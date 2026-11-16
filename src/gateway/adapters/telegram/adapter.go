package telegram

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"assistant/src/gateway"
)

// TelegramAdapter consumes the Modular Observer API and delivers throttled progress updates to Telegram.
type TelegramAdapter struct {
	client           BotClient
	chatID           int64
	throttleInterval time.Duration

	mu            sync.Mutex
	statusMsgID   int
	lastEditTime     time.Time
	pendingEdit      bool
	lastRenderedText string
	currentPhase     gateway.ExecutionPhase
	activeWorker  string
	activeSubtask string
	activeTool    string
	planSummary   string
	answerBuffer  strings.Builder
	finalized     bool
	closed        bool
}

// NewTelegramAdapter constructs a TelegramAdapter observer for the specified chat.
func NewTelegramAdapter(cfg Config) (*TelegramAdapter, error) {
	if cfg.Client == nil {
		return nil, ErrClientNil
	}
	throttle := cfg.ThrottleInterval
	if throttle <= 0 {
		throttle = DefaultThrottleInterval
	}

	return &TelegramAdapter{
		client:           cfg.Client,
		chatID:           cfg.ChatID,
		throttleInterval: throttle,
		currentPhase:     gateway.PhaseIdle,
	}, nil
}

// OnEvent implements gateway.ExecutionObserver.
func (a *TelegramAdapter) OnEvent(ctx context.Context, ev gateway.OutboundEvent) {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.closed {
		return
	}

	switch ev.Type {
	case gateway.EventPhaseChange:
		a.currentPhase = ev.Phase
		a.requestThrottledEdit(ctx)

	case gateway.EventPlanCreated:
		if ev.Plan != nil {
			a.planSummary = fmt.Sprintf("%d subtasks planned", len(ev.Plan.SubTasks))
		}
		a.requestThrottledEdit(ctx)

	case gateway.EventSubtaskStart:
		if ev.Subtask != nil {
			a.activeWorker = ev.Subtask.Worker
			a.activeSubtask = fmt.Sprintf("%s: %s", ev.Subtask.SubtaskID, ev.Subtask.Description)
		}
		a.requestThrottledEdit(ctx)

	case gateway.EventSubtaskComplete:
		a.activeSubtask = ""
		a.requestThrottledEdit(ctx)

	case gateway.EventSubtaskFailed:
		if ev.Subtask != nil {
			a.activeSubtask = fmt.Sprintf("%s (failed: %s)", ev.Subtask.SubtaskID, ev.Subtask.Error)
		}
		a.requestThrottledEdit(ctx)

	case gateway.EventToolCall:
		if ev.ToolCall != nil {
			a.activeTool = ev.ToolCall.ToolName
		}
		a.requestThrottledEdit(ctx)

	case gateway.EventToolResult:
		a.activeTool = ""
		a.requestThrottledEdit(ctx)

	case gateway.EventTokenChunk:
		if a.finalized {
			return
		}
		if strings.EqualFold(ev.AgentName, "summarizer") && a.activeWorker != "summarizer" {
			a.answerBuffer.Reset()
			a.activeWorker = "summarizer"
		}
		a.answerBuffer.WriteString(ev.TextDelta)

	case gateway.EventHITLRequest:
		a.handleHITLPrompt(ctx, ev.HITL)

	case gateway.EventTurnComplete:
		if a.finalized {
			return
		}
		// Guard against stray inner worker completions that lack orchestrator telemetry
		if ev.AgentName != "" && !strings.EqualFold(ev.AgentName, "orchestrator") && ev.Metrics == nil {
			return
		}
		a.finalized = true
		a.finalizeTurn(ctx, ev.Metrics)

	case gateway.EventTurnError:
		if a.finalized {
			return
		}
		a.finalized = true
		a.handleError(ctx, ev.Error)
	}
}

// Close gracefully stops the observer.
func (a *TelegramAdapter) Close() {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.closed = true
}

func (a *TelegramAdapter) requestThrottledEdit(ctx context.Context) {
	now := time.Now()

	// If no status message has been created yet, send the initial status box
	if a.statusMsgID == 0 {
		text := a.buildStatusMessage()
		msgID, err := a.client.SendMessage(ctx, a.chatID, text)
		if err == nil {
			a.statusMsgID = msgID
			a.lastEditTime = now
			a.lastRenderedText = text
		}
		return
	}

	newText := a.buildStatusMessage()
	if newText == a.lastRenderedText {
		return
	}

	// Throttle status updates to avoid Telegram rate limits
	elapsed := now.Sub(a.lastEditTime)
	if elapsed >= a.throttleInterval {
		_ = a.client.EditMessageText(ctx, a.chatID, a.statusMsgID, newText)
		a.lastEditTime = now
		a.lastRenderedText = newText
		a.pendingEdit = false
	} else if !a.pendingEdit {
		a.pendingEdit = true
		time.AfterFunc(a.throttleInterval-elapsed, func() {
			a.mu.Lock()
			defer a.mu.Unlock()
			if a.pendingEdit && a.statusMsgID != 0 && !a.closed {
				deferredText := a.buildStatusMessage()
				if deferredText != a.lastRenderedText {
					_ = a.client.EditMessageText(context.Background(), a.chatID, a.statusMsgID, deferredText)
					a.lastRenderedText = deferredText
					a.lastEditTime = time.Now()
				}
				a.pendingEdit = false
			}
		})
	}
}

func (a *TelegramAdapter) buildStatusMessage() string {
	return FormatStatus(a.currentPhase, a.planSummary, a.activeWorker, a.activeSubtask, a.activeTool)
}

func (a *TelegramAdapter) handleHITLPrompt(ctx context.Context, hitl *gateway.HITLApprovalPrompt) {
	if hitl == nil {
		return
	}
	text, markup := FormatHITLPrompt(hitl)
	_, _ = a.client.SendMessageWithMarkup(ctx, a.chatID, text, markup)
}

func (a *TelegramAdapter) finalizeTurn(ctx context.Context, metrics *gateway.TurnMetrics) {
	finalAnswer := a.answerBuffer.String()
	if strings.TrimSpace(finalAnswer) == "" {
		finalAnswer = "Turn completed successfully."
	}

	if a.statusMsgID != 0 {
		_ = a.client.EditMessageText(ctx, a.chatID, a.statusMsgID, "✔ *Turn completed successfully.*")
	}

	chunks := SplitMessage(finalAnswer, DefaultMaxMessageLength)
	for _, chunk := range chunks {
		_, _ = a.client.SendMessage(ctx, a.chatID, chunk)
	}

	if metrics != nil {
		footer := FormatMetrics(metrics)
		if footer != "" {
			_, _ = a.client.SendMessage(ctx, a.chatID, footer)
		}
	}
}

func (a *TelegramAdapter) handleError(ctx context.Context, errMsg string) {
	msg := fmt.Sprintf("✖ *Error:* %s", errMsg)
	if a.statusMsgID != 0 {
		_ = a.client.EditMessageText(ctx, a.chatID, a.statusMsgID, msg)
	} else {
		_, _ = a.client.SendMessage(ctx, a.chatID, msg)
	}
}

package telegram

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"assistant/src/gateway"
)

// TurnRunner executes a single turn lifecycle between Gateway and a Telegram chat.
type TurnRunner struct {
	gw               *gateway.Gateway
	client           BotClient
	chatID           int64
	userID           int64
	sessionID        string
	prompt           string
	throttleInterval time.Duration
	sessionMgr       *SessionManager
	maxMessageLength int

	mu               sync.Mutex
	statusMsgID      int
	lastEditTime     time.Time
	pendingEdit      bool
	lastRenderedText string
	currentPhase     gateway.ExecutionPhase
	activeWorker     string
	activeSubtask    string
	activeTool       string
	planSummary      string
	answerBuffer     strings.Builder
	finalized        bool
}

// NewTurnRunner constructs a TurnRunner for a single inbound Telegram request.
func NewTurnRunner(
	gw *gateway.Gateway,
	client BotClient,
	chatID int64,
	userID int64,
	sessionID string,
	prompt string,
	throttleInterval time.Duration,
	sessionMgr *SessionManager,
	maxLen int,
) *TurnRunner {
	if throttleInterval <= 0 {
		throttleInterval = DefaultThrottleInterval
	}
	if maxLen <= 0 {
		maxLen = DefaultMaxMessageLength
	}
	return &TurnRunner{
		gw:               gw,
		client:           client,
		chatID:           chatID,
		userID:           userID,
		sessionID:        sessionID,
		prompt:           prompt,
		throttleInterval: throttleInterval,
		sessionMgr:       sessionMgr,
		maxMessageLength: maxLen,
		currentPhase:     gateway.PhasePlanning,
	}
}

// Run submits the turn to the Gateway and processes the outbound event stream to completion.
func (r *TurnRunner) Run(ctx context.Context) error {
	rawReq := gateway.InboundTurnRequest{
		SessionID: r.sessionID,
		UserID:    fmt.Sprintf("telegram:%d", r.userID),
		Channel:   gateway.ClientTypeTelegram,
		Trigger:   gateway.TriggerInteractive,
		Prompt:    r.prompt,
	}

	eventCh, _, err := r.gw.SubmitTurn(ctx, rawReq)
	if err != nil {
		r.sendErrorMessage(ctx, fmt.Sprintf("Failed to initiate turn: %v", err))
		return err
	}

	// Start typing heartbeat
	heartbeatDone := make(chan struct{})
	defer close(heartbeatDone)
	go r.runTypingHeartbeat(ctx, heartbeatDone)

	// Send initial status message
	initialStatus := FormatStatus(r.currentPhase, "", "", "", "")
	if msgID, err := r.client.SendMessage(ctx, r.chatID, initialStatus); err == nil {
		r.mu.Lock()
		r.statusMsgID = msgID
		r.lastEditTime = time.Now()
		r.lastRenderedText = initialStatus
		r.mu.Unlock()
	}

	// Process event stream
	for ev := range eventCh {
		r.handleEvent(ctx, ev)
	}

	return nil
}

func (r *TurnRunner) runTypingHeartbeat(ctx context.Context, done <-chan struct{}) {
	_ = r.client.SendChatAction(ctx, r.chatID, string(ActionTyping))
	ticker := time.NewTicker(4 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-done:
			return
		case <-ctx.Done():
			return
		case <-ticker.C:
			_ = r.client.SendChatAction(ctx, r.chatID, string(ActionTyping))
		}
	}
}

func (r *TurnRunner) handleEvent(ctx context.Context, ev gateway.OutboundEvent) {
	r.mu.Lock()
	defer r.mu.Unlock()

	switch ev.Type {
	case gateway.EventPhaseChange:
		r.currentPhase = ev.Phase
		r.requestThrottledEditLocked(ctx)

	case gateway.EventPlanCreated:
		if ev.Plan != nil {
			r.planSummary = fmt.Sprintf("%d subtasks planned", len(ev.Plan.SubTasks))
		}
		r.requestThrottledEditLocked(ctx)

	case gateway.EventSubtaskStart:
		if ev.Subtask != nil {
			r.activeWorker = ev.Subtask.Worker
			r.activeSubtask = fmt.Sprintf("%s: %s", ev.Subtask.SubtaskID, ev.Subtask.Description)
		}
		r.requestThrottledEditLocked(ctx)

	case gateway.EventSubtaskComplete:
		r.activeSubtask = ""
		r.requestThrottledEditLocked(ctx)

	case gateway.EventSubtaskFailed:
		if ev.Subtask != nil {
			r.activeSubtask = fmt.Sprintf("%s (failed: %s)", ev.Subtask.SubtaskID, ev.Subtask.Error)
		}
		r.requestThrottledEditLocked(ctx)

	case gateway.EventToolCall:
		if ev.ToolCall != nil {
			r.activeTool = ev.ToolCall.ToolName
		}
		r.requestThrottledEditLocked(ctx)

	case gateway.EventToolResult:
		r.activeTool = ""
		r.requestThrottledEditLocked(ctx)

	case gateway.EventTokenChunk:
		if r.finalized {
			return
		}
		if strings.EqualFold(ev.AgentName, "summarizer") && r.activeWorker != "summarizer" {
			r.answerBuffer.Reset()
			r.activeWorker = "summarizer"
		}
		r.answerBuffer.WriteString(ev.TextDelta)

	case gateway.EventHITLRequest:
		r.handleHITLPromptLocked(ctx, ev.HITL)

	case gateway.EventTurnComplete:
		if r.finalized {
			return
		}
		// Guard against stray inner worker completions that lack orchestrator telemetry
		if ev.AgentName != "" && !strings.EqualFold(ev.AgentName, "orchestrator") && ev.Metrics == nil {
			return
		}
		r.finalized = true
		r.finalizeTurnLocked(ctx, ev.Metrics)

	case gateway.EventTurnError:
		if r.finalized {
			return
		}
		r.finalized = true
		r.sendErrorMessageLocked(ctx, ev.Error)
	}
}

func (r *TurnRunner) requestThrottledEditLocked(ctx context.Context) {
	if r.statusMsgID == 0 {
		return
	}

	newText := FormatStatus(r.currentPhase, r.planSummary, r.activeWorker, r.activeSubtask, r.activeTool)
	if newText == r.lastRenderedText {
		return
	}

	now := time.Now()
	elapsed := now.Sub(r.lastEditTime)
	if elapsed >= r.throttleInterval {
		_ = r.client.EditMessageText(ctx, r.chatID, r.statusMsgID, newText)
		r.lastEditTime = now
		r.lastRenderedText = newText
		r.pendingEdit = false
	} else if !r.pendingEdit {
		r.pendingEdit = true
		time.AfterFunc(r.throttleInterval-elapsed, func() {
			r.mu.Lock()
			defer r.mu.Unlock()
			if r.pendingEdit && r.statusMsgID != 0 {
				deferredText := FormatStatus(r.currentPhase, r.planSummary, r.activeWorker, r.activeSubtask, r.activeTool)
				if deferredText != r.lastRenderedText {
					_ = r.client.EditMessageText(context.Background(), r.chatID, r.statusMsgID, deferredText)
					r.lastRenderedText = deferredText
					r.lastEditTime = time.Now()
				}
				r.pendingEdit = false
			}
		})
	}
}

func (r *TurnRunner) handleHITLPromptLocked(ctx context.Context, hitl *gateway.HITLApprovalPrompt) {
	if hitl == nil {
		return
	}
	if r.sessionMgr != nil {
		r.sessionMgr.SetPendingHITL(r.chatID, hitl.RequestID)
	}

	text, markup := FormatHITLPrompt(hitl)
	_, _ = r.client.SendMessageWithMarkup(ctx, r.chatID, text, markup)
}

func (r *TurnRunner) finalizeTurnLocked(ctx context.Context, metrics *gateway.TurnMetrics) {
	if r.statusMsgID != 0 {
		_ = r.client.EditMessageText(ctx, r.chatID, r.statusMsgID, "✔ *Turn completed successfully.*")
	}

	finalAnswer := r.answerBuffer.String()
	if strings.TrimSpace(finalAnswer) == "" {
		finalAnswer = "Turn completed successfully."
	}

	chunks := SplitMessage(finalAnswer, r.maxMessageLength)
	for _, chunk := range chunks {
		_, _ = r.client.SendMessage(ctx, r.chatID, chunk)
	}

	if metrics != nil {
		footer := FormatMetrics(metrics)
		if footer != "" {
			_, _ = r.client.SendMessage(ctx, r.chatID, footer)
		}
	}
}

func (r *TurnRunner) sendErrorMessage(ctx context.Context, errMsg string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.sendErrorMessageLocked(ctx, errMsg)
}

func (r *TurnRunner) sendErrorMessageLocked(ctx context.Context, errMsg string) {
	msg := fmt.Sprintf("✖ *Error:* %s", errMsg)
	if r.statusMsgID != 0 {
		_ = r.client.EditMessageText(ctx, r.chatID, r.statusMsgID, msg)
	} else {
		_, _ = r.client.SendMessage(ctx, r.chatID, msg)
	}
}

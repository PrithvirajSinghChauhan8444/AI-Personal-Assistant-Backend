package telegram

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"assistant/src/gateway"
)

// BotClient abstracts Telegram Bot API network calls for testability and flexibility.
type BotClient interface {
	SendMessage(ctx context.Context, chatID int64, text string) (int, error)
	EditMessageText(ctx context.Context, chatID int64, messageID int, text string) error
}

// HTTPBotClient interacts directly with the official Telegram Bot HTTP API.
type HTTPBotClient struct {
	token      string
	httpClient *http.Client
}

// NewHTTPBotClient creates a real Telegram Bot client.
func NewHTTPBotClient(token string, httpClient *http.Client) *HTTPBotClient {
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 10 * time.Second}
	}
	return &HTTPBotClient{
		token:      token,
		httpClient: httpClient,
	}
}

func (c *HTTPBotClient) SendMessage(ctx context.Context, chatID int64, text string) (int, error) {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", c.token)
	body, _ := json.Marshal(map[string]interface{}{
		"chat_id":    chatID,
		"text":       text,
		"parse_mode": "Markdown",
	})

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return 0, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return 0, fmt.Errorf("telegram sendMessage failed with status %d", resp.StatusCode)
	}

	var res struct {
		OK     bool `json:"ok"`
		Result struct {
			MessageID int `json:"message_id"`
		} `json:"result"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return 0, err
	}
	return res.Result.MessageID, nil
}

func (c *HTTPBotClient) EditMessageText(ctx context.Context, chatID int64, messageID int, text string) error {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/editMessageText", c.token)
	body, _ := json.Marshal(map[string]interface{}{
		"chat_id":    chatID,
		"message_id": messageID,
		"text":       text,
		"parse_mode": "Markdown",
	})

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return fmt.Errorf("telegram editMessageText failed with status %d", resp.StatusCode)
	}
	return nil
}

// MockBotClient records operations for unit testing.
type MockBotClient struct {
	mu           sync.Mutex
	SentMessages []string
	EditedTexts  []string
	NextMsgID    int
}

// NewMockBotClient creates an in-memory test double.
func NewMockBotClient() *MockBotClient {
	return &MockBotClient{
		NextMsgID: 100,
	}
}

func (m *MockBotClient) SendMessage(ctx context.Context, chatID int64, text string) (int, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.NextMsgID++
	m.SentMessages = append(m.SentMessages, text)
	return m.NextMsgID, nil
}

func (m *MockBotClient) EditMessageText(ctx context.Context, chatID int64, messageID int, text string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.EditedTexts = append(m.EditedTexts, text)
	return nil
}

// GetSentMessages returns a thread-safe copy of all sent messages.
func (m *MockBotClient) GetSentMessages() []string {
	m.mu.Lock()
	defer m.mu.Unlock()
	copied := make([]string, len(m.SentMessages))
	copy(copied, m.SentMessages)
	return copied
}

// GetEditedTexts returns a thread-safe copy of all edited message texts.
func (m *MockBotClient) GetEditedTexts() []string {
	m.mu.Lock()
	defer m.mu.Unlock()
	copied := make([]string, len(m.EditedTexts))
	copy(copied, m.EditedTexts)
	return copied
}

// Config holds options for TelegramAdapter.
type Config struct {
	Client           BotClient
	ChatID           int64
	ThrottleInterval time.Duration
}

// TelegramAdapter consumes the Modular Observer API and delivers throttled progress updates to Telegram.
type TelegramAdapter struct {
	client           BotClient
	chatID           int64
	throttleInterval time.Duration

	mu             sync.Mutex
	statusMsgID    int
	lastEditTime   time.Time
	pendingEdit    bool
	currentPhase   gateway.ExecutionPhase
	activeWorker   string
	activeSubtask  string
	activeTool     string
	planSummary    string
	answerBuffer   strings.Builder
	closed         bool
}

// NewTelegramAdapter constructs a TelegramAdapter.
func NewTelegramAdapter(cfg Config) (*TelegramAdapter, error) {
	if cfg.Client == nil {
		return nil, errors.New("bot client cannot be nil")
	}
	if cfg.ThrottleInterval <= 0 {
		cfg.ThrottleInterval = 1 * time.Second
	}

	adapter := &TelegramAdapter{
		client:           cfg.Client,
		chatID:           cfg.ChatID,
		throttleInterval: cfg.ThrottleInterval,
		currentPhase:     gateway.PhaseIdle,
	}

	return adapter, nil
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
		a.answerBuffer.WriteString(ev.TextDelta)

	case gateway.EventHITLRequest:
		a.handleHITLPrompt(ctx, ev.HITL)

	case gateway.EventTurnComplete:
		a.finalizeTurn(ctx, ev.Metrics)

	case gateway.EventTurnError:
		a.handleError(ctx, ev.Error)
	}
}

func (a *TelegramAdapter) requestThrottledEdit(ctx context.Context) {
	now := time.Now()

	// If we don't have a status message ID yet, create one
	if a.statusMsgID == 0 {
		text := a.buildStatusMessage()
		msgID, err := a.client.SendMessage(ctx, a.chatID, text)
		if err == nil {
			a.statusMsgID = msgID
			a.lastEditTime = now
		}
		return
	}

	// Throttle message edits to respect Telegram's rate limit
	elapsed := now.Sub(a.lastEditTime)
	if elapsed >= a.throttleInterval {
		text := a.buildStatusMessage()
		_ = a.client.EditMessageText(ctx, a.chatID, a.statusMsgID, text)
		a.lastEditTime = now
		a.pendingEdit = false
	} else {
		if !a.pendingEdit {
			a.pendingEdit = true
			time.AfterFunc(a.throttleInterval-elapsed, func() {
				a.mu.Lock()
				defer a.mu.Unlock()
				if a.pendingEdit && a.statusMsgID != 0 && !a.closed {
					text := a.buildStatusMessage()
					_ = a.client.EditMessageText(context.Background(), a.chatID, a.statusMsgID, text)
					a.lastEditTime = time.Now()
					a.pendingEdit = false
				}
			})
		}
	}
}

func (a *TelegramAdapter) buildStatusMessage() string {
	var sb strings.Builder
	sb.WriteString("🤖 *AI Assistant — Processing*\n")
	sb.WriteString(fmt.Sprintf("• *Phase:* `%s`\n", a.currentPhase))

	if a.planSummary != "" {
		sb.WriteString(fmt.Sprintf("• *Plan:* %s\n", a.planSummary))
	}
	if a.activeWorker != "" {
		sb.WriteString(fmt.Sprintf("• *Active Worker:* `%s`\n", a.activeWorker))
	}
	if a.activeSubtask != "" {
		sb.WriteString(fmt.Sprintf("• *Task:* %s\n", a.activeSubtask))
	}
	if a.activeTool != "" {
		sb.WriteString(fmt.Sprintf("• *Tool in flight:* 🛠 `%s`\n", a.activeTool))
	}

	return sb.String()
}

func (a *TelegramAdapter) handleHITLPrompt(ctx context.Context, hitl *gateway.HITLApprovalPrompt) {
	if hitl == nil {
		return
	}
	msg := fmt.Sprintf("⚠️ *Approval Required*\n\nTool: `%s`\nReason: %s\n\n_Reply with Approve or Deny_",
		hitl.ToolName, hitl.Reason)
	_, _ = a.client.SendMessage(ctx, a.chatID, msg)
}

func (a *TelegramAdapter) finalizeTurn(ctx context.Context, metrics *gateway.TurnMetrics) {
	finalAnswer := a.answerBuffer.String()
	if finalAnswer == "" {
		finalAnswer = "Turn completed successfully."
	}

	// Update status message to done or deliver final answer
	if a.statusMsgID != 0 {
		doneStatus := "✔ *Turn completed successfully.*"
		_ = a.client.EditMessageText(ctx, a.chatID, a.statusMsgID, doneStatus)
	}

	// Deliver full conversational answer
	_, _ = a.client.SendMessage(ctx, a.chatID, finalAnswer)

	// If metrics available, send telemetry footer
	if metrics != nil {
		footer := fmt.Sprintf("📊 _Duration: %dms | Tokens: in=%d, out=%d_",
			metrics.TotalDurationMs, metrics.PromptTokens, metrics.CompletionTokens)
		_, _ = a.client.SendMessage(ctx, a.chatID, footer)
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

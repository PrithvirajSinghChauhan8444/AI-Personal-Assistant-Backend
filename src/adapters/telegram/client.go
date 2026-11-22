package telegram

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

// BotClient abstracts Telegram Bot API operations for testability and decoupling.
type BotClient interface {
	SendMessage(ctx context.Context, chatID int64, text string) (int, error)
	SendMessageWithMarkup(ctx context.Context, chatID int64, text string, markup *InlineKeyboardMarkup) (int, error)
	EditMessageText(ctx context.Context, chatID int64, messageID int, text string) error
	EditMessageTextWithMarkup(ctx context.Context, chatID int64, messageID int, text string, markup *InlineKeyboardMarkup) error
	SendChatAction(ctx context.Context, chatID int64, action string) error
	GetUpdates(ctx context.Context, offset int, timeout int) ([]Update, error)
	AnswerCallbackQuery(ctx context.Context, callbackQueryID string, text string) error
	SetMyCommands(ctx context.Context, commands []BotCommand) error
}

// HTTPBotClient implements BotClient using direct HTTP calls to api.telegram.org.
type HTTPBotClient struct {
	token      string
	apiClient  *http.Client
	pollClient *http.Client
	baseURL    string
}

// NewHTTPBotClient creates a real Telegram Bot client.
func NewHTTPBotClient(token string, httpClient *http.Client) *HTTPBotClient {
	apiClient := httpClient
	if apiClient == nil {
		apiClient = &http.Client{Timeout: 15 * time.Second}
	}
	// Long-polling client must not terminate prematurely before Telegram's poll timeout
	pollClient := &http.Client{Timeout: 0}

	return &HTTPBotClient{
		token:      token,
		apiClient:  apiClient,
		pollClient: pollClient,
		baseURL:    "https://api.telegram.org",
	}
}

// SetBaseURL overrides the API base URL (useful for testing or local Bot API servers).
func (c *HTTPBotClient) SetBaseURL(url string) {
	c.baseURL = url
}

func (c *HTTPBotClient) SendMessage(ctx context.Context, chatID int64, text string) (int, error) {
	return c.SendMessageWithMarkup(ctx, chatID, text, nil)
}

func (c *HTTPBotClient) SendMessageWithMarkup(ctx context.Context, chatID int64, text string, markup *InlineKeyboardMarkup) (int, error) {
	payload := map[string]interface{}{
		"chat_id":    chatID,
		"text":       text,
		"parse_mode": string(ParseModeMarkdown),
	}
	if markup != nil {
		payload["reply_markup"] = markup
	}

	var res struct {
		OK          bool   `json:"ok"`
		Description string `json:"description"`
		Result      struct {
			MessageID int `json:"message_id"`
		} `json:"result"`
	}

	err := c.postJSON(ctx, "sendMessage", payload, &res)
	if err == nil && res.OK {
		return res.Result.MessageID, nil
	}

	// Fallback: If Markdown parsing failed, retry as raw plain text without parse_mode
	if isEntityParseError(err, res.Description) {
		delete(payload, "parse_mode")
		fallbackErr := c.postJSON(ctx, "sendMessage", payload, &res)
		if fallbackErr == nil && res.OK {
			return res.Result.MessageID, nil
		}
	}

	if err != nil {
		return 0, err
	}
	return 0, fmt.Errorf("telegram sendMessage error: %s", res.Description)
}

func (c *HTTPBotClient) EditMessageText(ctx context.Context, chatID int64, messageID int, text string) error {
	return c.EditMessageTextWithMarkup(ctx, chatID, messageID, text, nil)
}

func (c *HTTPBotClient) EditMessageTextWithMarkup(ctx context.Context, chatID int64, messageID int, text string, markup *InlineKeyboardMarkup) error {
	payload := map[string]interface{}{
		"chat_id":    chatID,
		"message_id": messageID,
		"text":       text,
		"parse_mode": string(ParseModeMarkdown),
	}
	if markup != nil {
		payload["reply_markup"] = markup
	}

	var res struct {
		OK          bool   `json:"ok"`
		Description string `json:"description"`
	}

	err := c.postJSON(ctx, "editMessageText", payload, &res)
	if err == nil && res.OK {
		return nil
	}

	// If Telegram reports message is not modified, treat as success
	if strings.Contains(strings.ToLower(res.Description), "message is not modified") {
		return nil
	}

	// Fallback: If Markdown parsing failed, retry as raw plain text without parse_mode
	if isEntityParseError(err, res.Description) {
		delete(payload, "parse_mode")
		fallbackErr := c.postJSON(ctx, "editMessageText", payload, &res)
		if fallbackErr == nil && res.OK {
			return nil
		}
		if strings.Contains(strings.ToLower(res.Description), "message is not modified") {
			return nil
		}
	}

	if err != nil {
		return err
	}
	return fmt.Errorf("telegram editMessageText error: %s", res.Description)
}

func (c *HTTPBotClient) SendChatAction(ctx context.Context, chatID int64, action string) error {
	payload := map[string]interface{}{
		"chat_id": chatID,
		"action":  action,
	}

	var res struct {
		OK          bool   `json:"ok"`
		Description string `json:"description"`
	}

	if err := c.postJSON(ctx, "sendChatAction", payload, &res); err != nil {
		return err
	}
	if !res.OK {
		return fmt.Errorf("telegram sendChatAction error: %s", res.Description)
	}
	return nil
}

func (c *HTTPBotClient) GetUpdates(ctx context.Context, offset int, timeout int) ([]Update, error) {
	url := fmt.Sprintf("%s/bot%s/getUpdates?offset=%d&timeout=%d", c.baseURL, c.token, offset, timeout)

	// Dynamically scale context timeout to avoid client cut-off before server responds
	pollCtx, cancel := context.WithTimeout(ctx, time.Duration(timeout+15)*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(pollCtx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create getUpdates request: %w", err)
	}

	resp, err := c.pollClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("getUpdates request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("getUpdates returned status %d", resp.StatusCode)
	}

	var res struct {
		OK          bool     `json:"ok"`
		Result      []Update `json:"result"`
		Description string   `json:"description"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return nil, fmt.Errorf("failed to decode getUpdates response: %w", err)
	}
	if !res.OK {
		return nil, fmt.Errorf("telegram getUpdates error: %s", res.Description)
	}

	return res.Result, nil
}

func (c *HTTPBotClient) AnswerCallbackQuery(ctx context.Context, callbackQueryID string, text string) error {
	payload := map[string]interface{}{
		"callback_query_id": callbackQueryID,
		"text":              text,
	}

	var res struct {
		OK          bool   `json:"ok"`
		Description string `json:"description"`
	}

	if err := c.postJSON(ctx, "answerCallbackQuery", payload, &res); err != nil {
		return err
	}
	if !res.OK {
		return fmt.Errorf("telegram answerCallbackQuery error: %s", res.Description)
	}
	return nil
}

func (c *HTTPBotClient) SetMyCommands(ctx context.Context, commands []BotCommand) error {
	payload := map[string]interface{}{
		"commands": commands,
	}

	var res struct {
		OK          bool   `json:"ok"`
		Description string `json:"description"`
	}

	if err := c.postJSON(ctx, "setMyCommands", payload, &res); err != nil {
		return err
	}
	if !res.OK {
		return fmt.Errorf("telegram setMyCommands error: %s", res.Description)
	}
	return nil
}

func (c *HTTPBotClient) postJSON(ctx context.Context, method string, payload interface{}, target interface{}) error {
	url := fmt.Sprintf("%s/bot%s/%s", c.baseURL, c.token, method)
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to serialize %s payload: %w", method, err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create %s request: %w", method, err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.apiClient.Do(req)
	if err != nil {
		return fmt.Errorf("%s network request failed: %w", method, err)
	}
	defer resp.Body.Close()

	// Handle 429 Too Many Requests backoff
	if resp.StatusCode == 429 {
		data, _ := io.ReadAll(resp.Body)
		var rateRes struct {
			Parameters struct {
				RetryAfter int `json:"retry_after"`
			} `json:"parameters"`
		}
		_ = json.Unmarshal(data, &rateRes)
		retrySec := rateRes.Parameters.RetryAfter
		if retrySec <= 0 || retrySec > 10 {
			retrySec = 2
		}
		select {
		case <-time.After(time.Duration(retrySec) * time.Second):
			// Retry once after backoff
			retryReq, retryErr := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
			if retryErr == nil {
				retryReq.Header.Set("Content-Type", "application/json")
				retryResp, doErr := c.apiClient.Do(retryReq)
				if doErr == nil {
					defer retryResp.Body.Close()
					return json.NewDecoder(retryResp.Body).Decode(target)
				}
			}
		case <-ctx.Done():
			return ctx.Err()
		}
		return fmt.Errorf("%s rate limited (429)", method)
	}

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read %s response body: %w", method, err)
	}

	return json.Unmarshal(data, target)
}

func isEntityParseError(err error, description string) bool {
	desc := strings.ToLower(description)
	if strings.Contains(desc, "can't parse entities") ||
		strings.Contains(desc, "entity starting at byte offset") ||
		strings.Contains(desc, "unmatched") ||
		strings.Contains(desc, "bad request") {
		return true
	}
	if err != nil {
		errStr := strings.ToLower(err.Error())
		return strings.Contains(errStr, "can't parse entities") ||
			strings.Contains(errStr, "status 400")
	}
	return false
}

// MockBotClient records operations for unit testing.
type MockBotClient struct {
	mu                 sync.Mutex
	SentMessages       []string
	SentMarkups        []*InlineKeyboardMarkup
	EditedTexts        []string
	ChatActions        []string
	NextMsgID          int
	UpdatesQueue       []Update
	Callbacks          []string
	RegisteredCommands []BotCommand
}

// NewMockBotClient creates an in-memory test double for unit testing.
func NewMockBotClient() *MockBotClient {
	return &MockBotClient{
		NextMsgID: 100,
	}
}

func (m *MockBotClient) SendMessage(ctx context.Context, chatID int64, text string) (int, error) {
	return m.SendMessageWithMarkup(ctx, chatID, text, nil)
}

func (m *MockBotClient) SendMessageWithMarkup(ctx context.Context, chatID int64, text string, markup *InlineKeyboardMarkup) (int, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.NextMsgID++
	m.SentMessages = append(m.SentMessages, text)
	m.SentMarkups = append(m.SentMarkups, markup)
	return m.NextMsgID, nil
}

func (m *MockBotClient) EditMessageText(ctx context.Context, chatID int64, messageID int, text string) error {
	return m.EditMessageTextWithMarkup(ctx, chatID, messageID, text, nil)
}

func (m *MockBotClient) EditMessageTextWithMarkup(ctx context.Context, chatID int64, messageID int, text string, markup *InlineKeyboardMarkup) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.EditedTexts = append(m.EditedTexts, text)
	return nil
}

func (m *MockBotClient) SendChatAction(ctx context.Context, chatID int64, action string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.ChatActions = append(m.ChatActions, action)
	return nil
}

func (m *MockBotClient) GetUpdates(ctx context.Context, offset int, timeout int) ([]Update, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if len(m.UpdatesQueue) == 0 {
		return nil, nil
	}
	updates := m.UpdatesQueue
	m.UpdatesQueue = nil
	return updates, nil
}

func (m *MockBotClient) AnswerCallbackQuery(ctx context.Context, callbackQueryID string, text string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.Callbacks = append(m.Callbacks, fmt.Sprintf("%s:%s", callbackQueryID, text))
	return nil
}

func (m *MockBotClient) SetMyCommands(ctx context.Context, commands []BotCommand) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.RegisteredCommands = append([]BotCommand(nil), commands...)
	return nil
}

// QueueUpdates appends simulated updates for test retrieval.
func (m *MockBotClient) QueueUpdates(updates ...Update) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.UpdatesQueue = append(m.UpdatesQueue, updates...)
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

// GetChatActions returns a thread-safe copy of all chat actions sent.
func (m *MockBotClient) GetChatActions() []string {
	m.mu.Lock()
	defer m.mu.Unlock()
	copied := make([]string, len(m.ChatActions))
	copy(copied, m.ChatActions)
	return copied
}

// ErrClientNil indicates that no BotClient implementation was provided.
var ErrClientNil = errors.New("telegram: bot client cannot be nil")

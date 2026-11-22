package telegram

import (
	"context"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"assistant/src/gateway"
)

// BotService orchestrates the long-polling Telegram ingress daemon, security whitelisting,
// interactive commands, callback queries, and turn execution.
type BotService struct {
	client           BotClient
	gw               *gateway.Gateway
	sessionMgr       *SessionManager
	throttleInterval time.Duration
	pollingTimeout   time.Duration
	maxMessageLength int

	mu        sync.Mutex
	running   bool
	cancel    context.CancelFunc
	wg        sync.WaitGroup
	busyMu    sync.Mutex
	busyChats map[int64]bool
}

// NewBotService constructs a new BotService instance with the given configuration.
func NewBotService(cfg Config) (*BotService, error) {
	if cfg.Client == nil {
		return nil, ErrClientNil
	}
	if cfg.Gateway == nil {
		return nil, fmt.Errorf("telegram: gateway cannot be nil")
	}

	throttle := cfg.ThrottleInterval
	if throttle <= 0 {
		throttle = DefaultThrottleInterval
	}

	timeout := cfg.PollingTimeout
	if timeout <= 0 {
		timeout = DefaultPollingTimeout
	}

	maxLen := cfg.MaxMessageLength
	if maxLen <= 0 {
		maxLen = DefaultMaxMessageLength
	}

	return &BotService{
		client:           cfg.Client,
		gw:               cfg.Gateway,
		sessionMgr:       NewSessionManager(cfg.AllowedUserIDs),
		throttleInterval: throttle,
		pollingTimeout:   timeout,
		maxMessageLength: maxLen,
		busyChats:        make(map[int64]bool),
	}, nil
}

// Start initiates the long-polling ingress loop in a background goroutine.
func (s *BotService) Start(ctx context.Context) error {
	s.mu.Lock()
	if s.running {
		s.mu.Unlock()
		return fmt.Errorf("telegram: bot service is already running")
	}
	pollCtx, cancel := context.WithCancel(ctx)
	s.cancel = cancel
	s.running = true
	s.mu.Unlock()

	// Register commands with Telegram UI for the native [/] menu button
	commands := []BotCommand{
		{Command: "start", Description: "Start interacting with AI assistant"},
		{Command: "help", Description: "Show available commands & instructions"},
		{Command: "reset", Description: "Clear context and start fresh session"},
		{Command: "status", Description: "View live execution and active tasks"},
		{Command: "approve", Description: "Authorize a paused HITL action"},
		{Command: "deny", Description: "Reject a paused HITL action"},
	}
	_ = s.client.SetMyCommands(pollCtx, commands)

	s.wg.Add(1)
	go s.pollLoop(pollCtx)
	return nil
}

// Stop gracefully terminates the polling loop and waits for active handlers to drain.
func (s *BotService) Stop() {
	s.mu.Lock()
	if !s.running {
		s.mu.Unlock()
		return
	}
	s.running = false
	if s.cancel != nil {
		s.cancel()
	}
	s.mu.Unlock()

	s.wg.Wait()
}

// SessionManager returns the underlying session manager.
func (s *BotService) SessionManager() *SessionManager {
	return s.sessionMgr
}

func (s *BotService) isChatBusy(chatID int64) bool {
	s.busyMu.Lock()
	defer s.busyMu.Unlock()
	return s.busyChats[chatID]
}

func (s *BotService) tryAcquireChat(chatID int64) bool {
	s.busyMu.Lock()
	defer s.busyMu.Unlock()
	if s.busyChats[chatID] {
		return false
	}
	s.busyChats[chatID] = true
	return true
}

func (s *BotService) releaseChat(chatID int64) {
	s.busyMu.Lock()
	defer s.busyMu.Unlock()
	delete(s.busyChats, chatID)
}

func (s *BotService) pollLoop(ctx context.Context) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(os.Stderr, "Recovered from panic in telegram poll loop: %v\n", r)
		}
		s.wg.Done()
	}()

	offset := 0
	timeoutSec := int(s.pollingTimeout.Seconds())
	if timeoutSec <= 0 {
		timeoutSec = 30
	}

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		updates, err := s.client.GetUpdates(ctx, offset, timeoutSec)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			time.Sleep(1 * time.Second)
			continue
		}

		for _, update := range updates {
			if update.UpdateID >= offset {
				offset = update.UpdateID + 1
			}
			s.handleUpdate(ctx, update)
		}
	}
}

func (s *BotService) handleUpdate(ctx context.Context, update Update) {
	if update.Message != nil {
		s.handleMessage(ctx, update.Message)
	} else if update.CallbackQuery != nil {
		s.handleCallbackQuery(ctx, update.CallbackQuery)
	}
}

func (s *BotService) handleMessage(ctx context.Context, msg *Message) {
	if msg == nil || msg.Chat == nil || msg.From == nil {
		return
	}

	chatID := msg.Chat.ID
	userID := msg.From.ID
	isPrivate := msg.Chat.Type == "" || msg.Chat.Type == "private"
	text := strings.TrimSpace(msg.Text)

	// Check authorization
	if !s.sessionMgr.IsAuthorized(userID) {
		// Only send access denied in private chat or if user explicitly invoked a bot command
		if isPrivate || strings.HasPrefix(text, "/") {
			_, _ = s.client.SendMessage(ctx, chatID, FormatAccessDenied(userID))
		}
		return
	}

	if text == "" {
		return
	}

	if strings.HasPrefix(text, "/") {
		s.handleCommand(ctx, chatID, userID, text)
		return
	}

	// Handle simple approve/deny text replies to pending HITL requests
	if handled := s.checkPendingHITLTextReply(ctx, chatID, text); handled {
		return
	}

	// Guard against concurrent turns in the same chat
	if !s.tryAcquireChat(chatID) {
		_, _ = s.client.SendMessage(ctx, chatID, "⏳ A task is already in progress in this chat. Please wait for it to complete or use */reset*.")
		return
	}

	sessionID := s.sessionMgr.GetOrCreateSession(chatID)
	runner := NewTurnRunner(
		s.gw,
		s.client,
		chatID,
		userID,
		sessionID,
		text,
		s.throttleInterval,
		s.sessionMgr,
		s.maxMessageLength,
	)

	s.wg.Add(1)
	go func() {
		defer func() {
			s.releaseChat(chatID)
			if r := recover(); r != nil {
				fmt.Fprintf(os.Stderr, "Recovered from panic in turn runner: %v\n", r)
			}
			s.wg.Done()
		}()
		_ = runner.Run(ctx)
	}()
}

func (s *BotService) handleCommand(ctx context.Context, chatID int64, userID int64, text string) {
	parts := strings.Fields(text)
	cmd := strings.ToLower(parts[0])
	if atIdx := strings.Index(cmd, "@"); atIdx != -1 {
		cmd = cmd[:atIdx] // Strip bot username suffix if present: /start@my_bot
	}

	switch cmd {
	case "/start":
		welcome := "👋 *Welcome to AI Personal Assistant*\n\n" + FormatHelp()
		_, _ = s.client.SendMessage(ctx, chatID, welcome)

	case "/help":
		_, _ = s.client.SendMessage(ctx, chatID, FormatHelp())

	case "/reset", "/clear", "/new":
		s.releaseChat(chatID)
		newSessID := s.sessionMgr.ResetSession(chatID)
		msg := fmt.Sprintf("🔄 *Session Reset*\nStarted fresh conversation session: `%s`", newSessID)
		_, _ = s.client.SendMessage(ctx, chatID, msg)

	case "/status":
		s.handleStatusCommand(ctx, chatID)

	case "/approve":
		feedback := strings.Join(parts[1:], " ")
		s.resolveHITL(ctx, chatID, true, feedback)

	case "/deny":
		feedback := strings.Join(parts[1:], " ")
		s.resolveHITL(ctx, chatID, false, feedback)

	default:
		_, _ = s.client.SendMessage(ctx, chatID, "❓ Unknown command. Send */help* for available options.")
	}
}

func (s *BotService) handleStatusCommand(ctx context.Context, chatID int64) {
	sessionID := s.sessionMgr.GetOrCreateSession(chatID)
	snap, err := s.gw.GetSnapshot(sessionID)
	if err != nil {
		_, _ = s.client.SendMessage(ctx, chatID, fmt.Sprintf("ℹ️ Session `%s` is currently idle.", sessionID))
		return
	}

	worker := snap.ActiveAgent
	tool := ""
	if snap.ActiveAction != nil {
		tool = snap.ActiveAction.Name
	}
	planText := ""
	if snap.Plan != nil {
		planText = fmt.Sprintf("%d subtasks planned", len(snap.Plan.SubTasks))
	}

	status := FormatStatus(snap.Phase, planText, worker, "", tool)
	_, _ = s.client.SendMessage(ctx, chatID, status)
}

func (s *BotService) checkPendingHITLTextReply(ctx context.Context, chatID int64, text string) bool {
	lower := strings.ToLower(text)
	if lower == "approve" || lower == "yes" {
		return s.resolveHITL(ctx, chatID, true, "")
	}
	if lower == "deny" || lower == "no" {
		return s.resolveHITL(ctx, chatID, false, "")
	}
	return false
}

func (s *BotService) resolveHITL(ctx context.Context, chatID int64, approved bool, feedback string) bool {
	reqID, ok := s.sessionMgr.GetPendingHITL(chatID)
	if !ok || reqID == "" {
		return false
	}

	s.sessionMgr.ClearPendingHITL(chatID)
	err := s.gw.RespondHITL(ctx, gateway.HITLResponse{
		RequestID:    reqID,
		Approved:     approved,
		UserFeedback: feedback,
		RespondedAt:  time.Now().UTC(),
	})

	if err != nil {
		_, _ = s.client.SendMessage(ctx, chatID, fmt.Sprintf("⚠️ Failed to submit HITL decision: %v", err))
		return true
	}

	verdict := "Approved"
	if !approved {
		verdict = "Denied"
	}
	_, _ = s.client.SendMessage(ctx, chatID, fmt.Sprintf("✔ Tool execution *%s* successfully.", verdict))
	return true
}

func (s *BotService) handleCallbackQuery(ctx context.Context, cb *CallbackQuery) {
	if cb == nil || cb.From == nil {
		return
	}

	userID := cb.From.ID
	if !s.sessionMgr.IsAuthorized(userID) {
		_ = s.client.AnswerCallbackQuery(ctx, cb.ID, "Unauthorized user")
		return
	}

	data := cb.Data
	if strings.HasPrefix(data, "hitl:approve:") {
		reqID := strings.TrimPrefix(data, "hitl:approve:")
		s.processCallbackHITL(ctx, cb, reqID, true)
	} else if strings.HasPrefix(data, "hitl:deny:") {
		reqID := strings.TrimPrefix(data, "hitl:deny:")
		s.processCallbackHITL(ctx, cb, reqID, false)
	}
}

func (s *BotService) processCallbackHITL(ctx context.Context, cb *CallbackQuery, reqID string, approved bool) {
	err := s.gw.RespondHITL(ctx, gateway.HITLResponse{
		RequestID:   reqID,
		Approved:    approved,
		RespondedAt: time.Now().UTC(),
	})

	if err != nil {
		_ = s.client.AnswerCallbackQuery(ctx, cb.ID, fmt.Sprintf("Error: %v", err))
		return
	}

	verdict := "Approved"
	if !approved {
		verdict = "Denied"
	}

	_ = s.client.AnswerCallbackQuery(ctx, cb.ID, fmt.Sprintf("Action %s", verdict))
	if cb.Message != nil && cb.Message.Chat != nil {
		s.sessionMgr.ClearPendingHITL(cb.Message.Chat.ID)
		updateText := fmt.Sprintf("✔ Decision recorded: *%s*", verdict)
		_ = s.client.EditMessageText(ctx, cb.Message.Chat.ID, cb.Message.MessageID, updateText)
	}
}

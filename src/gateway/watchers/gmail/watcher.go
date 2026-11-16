package gmail

import (
	"context"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"
)

// WatcherConfig defines timing and network parameters for an AccountWatcher.
type WatcherConfig struct {
	IMAPHost         string
	IdleTimeout      time.Duration
	KeepAliveCycle   time.Duration
	PollInterval     time.Duration
	BackoffMin       time.Duration
	BackoffMax       time.Duration
	SeenCacheLimit   int
}

// DefaultWatcherConfig returns balanced production defaults.
func DefaultWatcherConfig() WatcherConfig {
	return WatcherConfig{
		IMAPHost:       "imap.gmail.com:993",
		IdleTimeout:    25 * time.Second,
		KeepAliveCycle: 20 * time.Minute,
		PollInterval:   60 * time.Second,
		BackoffMin:     5 * time.Second,
		BackoffMax:     60 * time.Second,
		SeenCacheLimit: 500,
	}
}

// Dependencies encapsulates external collaborators for the watcher.
type Dependencies struct {
	Tokens     TokenProvider
	Fetcher    MailFetcher
	Stream     IMAPStream
	Classifier *EmailClassifier
	Gateway    TurnDispatcher
}

// AccountWatcher maintains a persistent IMAP IDLE connection for a single account.
type AccountWatcher struct {
	mu         sync.RWMutex
	account    WatchedAccount
	config     WatcherConfig
	deps       Dependencies
	status     WatcherStatus
	cancel     context.CancelFunc
	wg         sync.WaitGroup
	seenIDs    map[string]time.Time
	seenOrder  []string
	sessionID  string
}

// NewAccountWatcher initializes a watcher instance for a specific Google account.
func NewAccountWatcher(account WatchedAccount, cfg WatcherConfig, deps Dependencies) *AccountWatcher {
	if cfg.IMAPHost == "" {
		cfg = DefaultWatcherConfig()
	}
	return &AccountWatcher{
		account:   account,
		config:    cfg,
		deps:      deps,
		status:    StatusStopped,
		seenIDs:   make(map[string]time.Time),
		seenOrder: make([]string, 0, cfg.SeenCacheLimit),
	}
}

// Name returns the identifier for this account watcher.
func (w *AccountWatcher) Name() string {
	return fmt.Sprintf("gmail_watcher_%s", w.account.Alias)
}

// Status returns current lifecycle status safely.
func (w *AccountWatcher) Status() WatcherStatus {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return w.status
}

// SetSessionID binds the watcher to an active session conduit.
func (w *AccountWatcher) SetSessionID(sessionID string) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.sessionID = sessionID
}

// GetSessionID retrieves the currently bound session ID.
func (w *AccountWatcher) GetSessionID() string {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return w.sessionID
}

// Start spawns the background monitoring loop.
func (w *AccountWatcher) Start(ctx context.Context) error {
	w.mu.Lock()
	if w.status == StatusRunning {
		w.mu.Unlock()
		return nil
	}

	watchCtx, cancel := context.WithCancel(ctx)
	w.cancel = cancel
	w.status = StatusStarting
	w.mu.Unlock()

	w.wg.Add(1)
	go w.runSupervisor(watchCtx)

	return nil
}

// Stop cleanly terminates the watcher loop.
func (w *AccountWatcher) Stop() error {
	w.mu.Lock()
	if w.cancel != nil {
		w.cancel()
	}
	w.status = StatusStopped
	w.mu.Unlock()

	if w.deps.Stream != nil {
		_ = w.deps.Stream.Close()
	}

	w.wg.Wait()
	return nil
}

func (w *AccountWatcher) runSupervisor(ctx context.Context) {
	defer w.wg.Done()
	backoff := w.config.BackoffMin

	for {
		select {
		case <-ctx.Done():
			return
		default:
			err := w.runWatchSession(ctx)
			if err != nil && ctx.Err() == nil {
				w.setStatus(StatusError)
				errStr := err.Error()
				if strings.Contains(errStr, "invalid_grant") || strings.Contains(errStr, "expired or revoked") {
					fmt.Fprintf(os.Stderr, "⚠️ [Gmail Watcher %s] OAuth token is expired or revoked. Disabling watcher for %s until re-authenticated via scripts/auth_google.py --account %s\n", w.account.Alias, w.account.Alias, w.account.Alias)
					return // Permanent auth failure: terminate goroutine rather than spamming
				}
				fmt.Fprintf(os.Stderr, "⚠️ [Gmail Watcher %s] Session error: %v (retrying in %v)\n", w.account.Alias, err, backoff)
				select {
				case <-ctx.Done():
					return
				case <-time.After(backoff):
				}
				backoff = minDuration(backoff*2, w.config.BackoffMax)
			} else {
				backoff = w.config.BackoffMin
			}
		}
	}
}

func (w *AccountWatcher) runWatchSession(ctx context.Context) error {
	token, err := w.deps.Tokens.GetAccessToken(ctx, w.account.Alias)
	if err != nil {
		return fmt.Errorf("token error for %s: %w", w.account.Alias, err)
	}

	if w.deps.Stream == nil {
		w.deps.Stream = NewTLSIMAPStream()
	}

	if err := w.establishIMAP(ctx, token); err != nil {
		// Fallback to REST polling if IMAP protocol is unavailable
		return w.pollFallback(ctx)
	}

	w.setStatus(StatusRunning)
	return w.idleEventLoop(ctx)
}

func (w *AccountWatcher) establishIMAP(ctx context.Context, token string) error {
	if err := w.deps.Stream.Connect(ctx, w.config.IMAPHost); err != nil {
		return err
	}
	if err := w.deps.Stream.AuthenticateXOAUTH2(w.account.Email, token); err != nil {
		_ = w.deps.Stream.Close()
		return err
	}
	if err := w.deps.Stream.SelectMailbox("INBOX"); err != nil {
		_ = w.deps.Stream.Close()
		return err
	}
	return nil
}

func (w *AccountWatcher) idleEventLoop(ctx context.Context) error {
	cycleStart := time.Now()

	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}

		// Re-cycle connection periodically to prevent Google IMAP timeout
		if time.Since(cycleStart) >= w.config.KeepAliveCycle {
			_ = w.deps.Stream.ExitIDLE()
			return nil
		}

		if err := w.deps.Stream.EnterIDLE(); err != nil {
			return err
		}

		hasUpdate, err := w.deps.Stream.WaitForUpdate(ctx, w.config.IdleTimeout)
		if err != nil {
			return err
		}

		if hasUpdate {
			_ = w.deps.Stream.ExitIDLE()
			w.handleMailboxUpdate(ctx)
		}
	}
}

func (w *AccountWatcher) handleMailboxUpdate(ctx context.Context) {
	if w.deps.Fetcher == nil {
		return
	}

	emails, err := w.deps.Fetcher.FetchUnread(ctx, w.account.Alias, 5)
	if err != nil || len(emails) == 0 {
		return
	}

	for _, msg := range emails {
		if w.markSeen(msg.ID) {
			w.dispatchEmailTurn(ctx, msg)
		}
	}
}

func (w *AccountWatcher) pollFallback(ctx context.Context) error {
	w.setStatus(StatusRunning)
	ticker := time.NewTicker(w.config.PollInterval)
	defer ticker.Stop()

	w.handleMailboxUpdate(ctx)

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			w.handleMailboxUpdate(ctx)
		}
	}
}

func (w *AccountWatcher) dispatchEmailTurn(ctx context.Context, msg EmailSummary) {
	if w.deps.Gateway == nil || w.deps.Classifier == nil {
		return
	}

	req := w.deps.Classifier.BuildInboundTurn(msg)
	w.mu.RLock()
	sessID := w.sessionID
	w.mu.RUnlock()
	if sessID != "" {
		req.SessionID = sessID
	}

	eventCh, _, err := w.deps.Gateway.SubmitTurn(ctx, req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "⚠️ [Gmail Watcher %s] Failed to submit email turn: %v\n", w.account.Alias, err)
		return
	}

	// Drain turn stream asynchronously to prevent blocking the gateway pipeline
	go func() {
		for range eventCh {
		}
	}()
}

func (w *AccountWatcher) markSeen(id string) bool {
	w.mu.Lock()
	defer w.mu.Unlock()

	if _, exists := w.seenIDs[id]; exists {
		return false
	}

	w.seenIDs[id] = time.Now()
	w.seenOrder = append(w.seenOrder, id)

	if len(w.seenOrder) > w.config.SeenCacheLimit {
		oldest := w.seenOrder[0]
		w.seenOrder = w.seenOrder[1:]
		delete(w.seenIDs, oldest)
	}

	return true
}

func (w *AccountWatcher) setStatus(status WatcherStatus) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.status = status
}

func minDuration(a, b time.Duration) time.Duration {
	if a < b {
		return a
	}
	return b
}

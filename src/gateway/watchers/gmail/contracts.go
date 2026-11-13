package gmail

import (
	"context"
	"time"

	"assistant/src/gateway"
)

// WatcherStatus represents the current lifecycle phase of an email watcher.
type WatcherStatus string

const (
	StatusStopped  WatcherStatus = "STOPPED"
	StatusStarting WatcherStatus = "STARTING"
	StatusRunning  WatcherStatus = "RUNNING"
	StatusError    WatcherStatus = "ERROR"
)

// Watcher defines the standard lifecycle contract for background daemons.
type Watcher interface {
	Name() string
	Start(ctx context.Context) error
	Stop() error
	Status() WatcherStatus
}

// WatchedAccount holds metadata for an authenticated Gmail account.
type WatchedAccount struct {
	Alias string `json:"alias"`
	Email string `json:"email"`
}

// EmailSummary encapsulates normalized metadata for an incoming email.
type EmailSummary struct {
	ID        string    `json:"id"`
	ThreadID  string    `json:"thread_id"`
	Account   string    `json:"account"`
	From      string    `json:"from"`
	To        string    `json:"to"`
	Subject   string    `json:"subject"`
	Snippet   string    `json:"snippet"`
	Date      time.Time `json:"date"`
	Body      string    `json:"body"`
}

// TurnDispatcher submits autonomous inbound turns to Layer 1 Gateway.
type TurnDispatcher interface {
	SubmitTurn(ctx context.Context, req gateway.InboundTurnRequest) (<-chan gateway.OutboundEvent, gateway.InboundTurnRequest, error)
}

// TokenProvider retrieves valid OAuth access tokens for configured accounts.
type TokenProvider interface {
	GetAccessToken(ctx context.Context, account string) (string, error)
}

// MailFetcher retrieves unread email details from an account.
type MailFetcher interface {
	FetchUnread(ctx context.Context, account string, limit int) ([]EmailSummary, error)
}

// IMAPStream encapsulates low-level IMAP wire communications.
type IMAPStream interface {
	Connect(ctx context.Context, host string) error
	AuthenticateXOAUTH2(email, token string) error
	SelectMailbox(mailbox string) error
	EnterIDLE() error
	WaitForUpdate(ctx context.Context, timeout time.Duration) (bool, error)
	ExitIDLE() error
	Close() error
}

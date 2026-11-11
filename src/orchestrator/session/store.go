package session

import (
	"context"

	"assistant/src/gateway"
)

// Store defines the persistence contract required by the Layer 2 Orchestrator.
type Store interface {
	// GetOrCreateSession retrieves an existing session or inserts a newly initialized record.
	GetOrCreateSession(ctx context.Context, sessionID, userID string, channel gateway.ClientType) (*Session, error)

	// AppendMessage appends a conversational turn message into the persistent timeline.
	AppendMessage(ctx context.Context, msg ChatMessage) error

	// GetSessionHistory retrieves up to `limit` chronologically ordered messages for the session.
	GetSessionHistory(ctx context.Context, sessionID string, limit int) ([]ChatMessage, error)

	// SaveCheckpoint records a suspended turn awaiting human-in-the-loop approval.
	SaveCheckpoint(ctx context.Context, cp Checkpoint) error

	// GetCheckpoint retrieves an existing checkpoint by its unique approval RequestID.
	GetCheckpoint(ctx context.Context, requestID string) (*Checkpoint, error)

	// UpdateCheckpointStatus transitions the state of a checkpoint (e.g. RESUMED, CANCELLED).
	UpdateCheckpointStatus(ctx context.Context, requestID string, status CheckpointStatus) error

	// RecordToolAudit logs security telemetry for an executed or evaluated tool action.
	RecordToolAudit(ctx context.Context, entry ToolAuditEntry) error

	// Close flushes open database connections.
	Close() error
}

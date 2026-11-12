package session

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"assistant/src/gateway"

	"github.com/google/uuid"
	_ "modernc.org/sqlite"
)

var (
	// ErrCheckpointNotFound is returned when an HITL approval request does not exist.
	ErrCheckpointNotFound = errors.New("checkpoint not found")
	// ErrEmptySessionID is returned when an invalid empty session identifier is provided.
	ErrEmptySessionID = errors.New("session id cannot be empty")
)

// SQLiteStore implements the Store interface backed by a local SQLite file.
type SQLiteStore struct {
	db *sql.DB
}

// NewSQLiteStore opens the SQLite database at dbPath and runs migrations.
func NewSQLiteStore(dbPath string) (*SQLiteStore, error) {
	if dbPath == "" {
		return nil, errors.New("dbPath cannot be empty")
	}

	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create db directory %q: %w", dir, err)
	}

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open sqlite database: %w", err)
	}

	// Configure connection pool for SQLite concurrency
	db.SetMaxOpenConns(1) // Avoid database locked errors with SQLite
	db.SetMaxIdleConns(1)

	store := &SQLiteStore{db: db}
	if err := store.initializePragmasAndSchema(); err != nil {
		_ = db.Close()
		return nil, err
	}

	return store, nil
}

func (s *SQLiteStore) initializePragmasAndSchema() error {
	pragmas := []string{
		"PRAGMA journal_mode = WAL;",
		"PRAGMA synchronous = NORMAL;",
		"PRAGMA foreign_keys = ON;",
		"PRAGMA busy_timeout = 5000;",
	}
	for _, pragma := range pragmas {
		if _, err := s.db.Exec(pragma); err != nil {
			return fmt.Errorf("failed to execute %q: %w", pragma, err)
		}
	}

	schema := `
	CREATE TABLE IF NOT EXISTS sessions (
		session_id TEXT PRIMARY KEY,
		user_id TEXT NOT NULL,
		channel TEXT NOT NULL,
		created_at TIMESTAMP NOT NULL,
		updated_at TIMESTAMP NOT NULL
	);

	CREATE TABLE IF NOT EXISTS messages (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL REFERENCES sessions(session_id),
		turn_id TEXT NOT NULL,
		role TEXT NOT NULL,
		agent_name TEXT NOT NULL,
		content TEXT NOT NULL,
		tool_calls_json TEXT,
		created_at TIMESTAMP NOT NULL
	);

	CREATE TABLE IF NOT EXISTS checkpoints (
		request_id TEXT PRIMARY KEY,
		session_id TEXT NOT NULL REFERENCES sessions(session_id),
		status TEXT NOT NULL,
		trigger_type TEXT NOT NULL,
		target_agent TEXT NOT NULL,
		pending_tool_name TEXT NOT NULL,
		pending_tool_args TEXT NOT NULL,
		turn_state_json TEXT NOT NULL,
		created_at TIMESTAMP NOT NULL,
		updated_at TIMESTAMP NOT NULL
	);

	CREATE TABLE IF NOT EXISTS tool_audit_log (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL REFERENCES sessions(session_id),
		turn_id TEXT NOT NULL,
		tool_name TEXT NOT NULL,
		risk_level TEXT NOT NULL,
		status TEXT NOT NULL,
		duration_ms INTEGER NOT NULL,
		created_at TIMESTAMP NOT NULL
	);

	CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id ASC);
	CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id, status);
	CREATE INDEX IF NOT EXISTS idx_tool_audit_session ON tool_audit_log(session_id);
	`

	if _, err := s.db.Exec(schema); err != nil {
		return fmt.Errorf("failed to initialize sqlite schema: %w", err)
	}

	return nil
}

// GetOrCreateSession retrieves an existing session or creates a new one if missing.
func (s *SQLiteStore) GetOrCreateSession(ctx context.Context, sessionID, userID string, channel gateway.ClientType) (*Session, error) {
	if sessionID == "" {
		sessionID = fmt.Sprintf("sess_%s", uuid.New().String()[:8])
	}
	if userID == "" {
		userID = "local:user"
	}
	if channel == "" {
		channel = gateway.ClientTypeCLI
	}

	now := time.Now().UTC()

	query := `
	INSERT INTO sessions (session_id, user_id, channel, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?)
	ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at
	RETURNING session_id, user_id, channel, created_at, updated_at;
	`

	var sess Session
	var chStr string
	err := s.db.QueryRowContext(ctx, query, sessionID, userID, string(channel), now, now).Scan(
		&sess.SessionID,
		&sess.UserID,
		&chStr,
		&sess.CreatedAt,
		&sess.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get or create session %q: %w", sessionID, err)
	}
	sess.Channel = gateway.ClientType(chStr)
	return &sess, nil
}

// AppendMessage records a single chat message into SQLite.
func (s *SQLiteStore) AppendMessage(ctx context.Context, msg ChatMessage) error {
	if msg.SessionID == "" {
		return ErrEmptySessionID
	}
	if msg.CreatedAt.IsZero() {
		msg.CreatedAt = time.Now().UTC()
	}

	query := `
	INSERT INTO messages (session_id, turn_id, role, agent_name, content, tool_calls_json, created_at)
	VALUES (?, ?, ?, ?, ?, ?, ?);
	`
	_, err := s.db.ExecContext(ctx, query,
		msg.SessionID,
		msg.TurnID,
		msg.Role,
		msg.AgentName,
		msg.Content,
		msg.ToolCallsJSON,
		msg.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to append message to session %q: %w", msg.SessionID, err)
	}
	return nil
}

// GetSessionHistory retrieves recent conversation messages up to the requested limit.
func (s *SQLiteStore) GetSessionHistory(ctx context.Context, sessionID string, limit int) ([]ChatMessage, error) {
	if sessionID == "" {
		return nil, ErrEmptySessionID
	}
	if limit <= 0 {
		limit = 50
	}

	query := `
	SELECT id, session_id, turn_id, role, agent_name, content, COALESCE(tool_calls_json, ''), created_at
	FROM messages
	WHERE session_id = ?
	ORDER BY id ASC
	LIMIT ?;
	`

	rows, err := s.db.QueryContext(ctx, query, sessionID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query messages for session %q: %w", sessionID, err)
	}
	defer rows.Close()

	var history []ChatMessage
	for rows.Next() {
		var m ChatMessage
		if err := rows.Scan(
			&m.ID,
			&m.SessionID,
			&m.TurnID,
			&m.Role,
			&m.AgentName,
			&m.Content,
			&m.ToolCallsJSON,
			&m.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan chat message: %w", err)
		}
		history = append(history, m)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error for session %q: %w", sessionID, err)
	}

	return history, nil
}

// SaveCheckpoint saves or updates a paused HITL checkpoint.
func (s *SQLiteStore) SaveCheckpoint(ctx context.Context, cp Checkpoint) error {
	now := time.Now().UTC()
	if cp.CreatedAt.IsZero() {
		cp.CreatedAt = now
	}
	cp.UpdatedAt = now

	query := `
	INSERT INTO checkpoints (
		request_id, session_id, status, trigger_type, target_agent,
		pending_tool_name, pending_tool_args, turn_state_json, created_at, updated_at
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	ON CONFLICT(request_id) DO UPDATE SET
		status = excluded.status,
		pending_tool_args = excluded.pending_tool_args,
		turn_state_json = excluded.turn_state_json,
		updated_at = excluded.updated_at;
	`

	_, err := s.db.ExecContext(ctx, query,
		cp.RequestID,
		cp.SessionID,
		string(cp.Status),
		string(cp.TriggerType),
		cp.TargetAgent,
		cp.PendingToolName,
		cp.PendingToolArgs,
		cp.TurnStateJSON,
		cp.CreatedAt,
		cp.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to save checkpoint %q: %w", cp.RequestID, err)
	}
	return nil
}

// GetCheckpoint retrieves an HITL checkpoint by requestID.
func (s *SQLiteStore) GetCheckpoint(ctx context.Context, requestID string) (*Checkpoint, error) {
	query := `
	SELECT request_id, session_id, status, trigger_type, target_agent,
	       pending_tool_name, pending_tool_args, turn_state_json, created_at, updated_at
	FROM checkpoints
	WHERE request_id = ?;
	`

	var cp Checkpoint
	var statusStr, triggerStr string
	err := s.db.QueryRowContext(ctx, query, requestID).Scan(
		&cp.RequestID,
		&cp.SessionID,
		&statusStr,
		&triggerStr,
		&cp.TargetAgent,
		&cp.PendingToolName,
		&cp.PendingToolArgs,
		&cp.TurnStateJSON,
		&cp.CreatedAt,
		&cp.UpdatedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrCheckpointNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("failed to read checkpoint %q: %w", requestID, err)
	}

	cp.Status = CheckpointStatus(statusStr)
	cp.TriggerType = gateway.TriggerType(triggerStr)
	return &cp, nil
}

// UpdateCheckpointStatus transitions the checkpoint status.
func (s *SQLiteStore) UpdateCheckpointStatus(ctx context.Context, requestID string, status CheckpointStatus) error {
	query := `
	UPDATE checkpoints
	SET status = ?, updated_at = ?
	WHERE request_id = ?;
	`
	result, err := s.db.ExecContext(ctx, query, string(status), time.Now().UTC(), requestID)
	if err != nil {
		return fmt.Errorf("failed to update checkpoint status %q: %w", requestID, err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return err
	}
	if rowsAffected == 0 {
		return ErrCheckpointNotFound
	}
	return nil
}

// RecordToolAudit appends an audit trail entry for tool executions.
func (s *SQLiteStore) RecordToolAudit(ctx context.Context, entry ToolAuditEntry) error {
	if entry.CreatedAt.IsZero() {
		entry.CreatedAt = time.Now().UTC()
	}

	query := `
	INSERT INTO tool_audit_log (session_id, turn_id, tool_name, risk_level, status, duration_ms, created_at)
	VALUES (?, ?, ?, ?, ?, ?, ?);
	`
	_, err := s.db.ExecContext(ctx, query,
		entry.SessionID,
		entry.TurnID,
		entry.ToolName,
		entry.RiskLevel,
		entry.Status,
		entry.DurationMs,
		entry.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to log tool audit: %w", err)
	}
	return nil
}

// DB returns the underlying SQLite database handle for shared persistence.
func (s *SQLiteStore) DB() *sql.DB {
	return s.db
}

// Close gracefully closes the SQLite database connection.
func (s *SQLiteStore) Close() error {
	if s.db != nil {
		return s.db.Close()
	}
	return nil
}

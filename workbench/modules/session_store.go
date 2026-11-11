package modules

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"time"

	"assistant/src/gateway"
	"assistant/src/orchestrator/session"
	"assistant/workbench/engine"

	"github.com/google/uuid"
)

func getWorkbenchStore() (session.Store, error) {
	dbDir := filepath.Join("workspace", "workbench", "data")
	_ = os.MkdirAll(dbDir, 0755)
	dbPath := filepath.Join(dbDir, "bench_sessions.db")
	return session.NewSQLiteStore(dbPath)
}

// GetOrCreateSessionInput defines input for creating/fetching sessions.
type GetOrCreateSessionInput struct {
	SessionID string             `json:"session_id" desc:"Session UUID (leave empty to generate new)"`
	UserID    string             `json:"user_id" desc:"User identifier, e.g. local:prit"`
	Channel   gateway.ClientType `json:"channel" enum:"CLI,WEB,TELEGRAM,INTERNAL" desc:"Client ingress channel"`
}

// AppendMessageInput defines input for appending messages.
type AppendMessageInput struct {
	SessionID string `json:"session_id" desc:"Target session UUID"`
	TurnID    string `json:"turn_id" desc:"Turn UUID"`
	Role      string `json:"role" enum:"user,assistant,system,tool" desc:"Message role"`
	AgentName string `json:"agent_name" desc:"Agent attribution (e.g. ManagerAgent)"`
	Content   string `json:"content" desc:"Message body text"`
}

// GetSessionHistoryInput defines input for retrieving session history.
type GetSessionHistoryInput struct {
	SessionID string `json:"session_id" desc:"Session UUID"`
	Limit     int    `json:"limit" desc:"Maximum number of past messages to retrieve"`
}

// RegisterSessionStore registers Session Store modules.
func RegisterSessionStore(r *engine.Registry) {
	// 1. GetOrCreateSession
	r.Register(engine.Module{
		ID:          "l2_session_store_get_or_create",
		Name:        "Layer 2: Session Store (GetOrCreateSession)",
		Category:    "Isolated Module",
		Description: "Fetches or inserts an active conversation session thread in SQLite.",
		InputType:   reflect.TypeOf(GetOrCreateSessionInput{}),
		Presets: []engine.Preset{
			{
				ID:       "create_new_session",
				Name:     "Create New CLI Session",
				Category: "Happy Path",
				Payload: GetOrCreateSessionInput{
					SessionID: uuid.New().String(),
					UserID:    "local:prit",
					Channel:   gateway.ClientTypeCLI,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var input GetOrCreateSessionInput
			if err := json.Unmarshal(inputRaw, &input); err != nil {
				return nil, err
			}

			store, err := getWorkbenchStore()
			if err != nil {
				return nil, err
			}
			defer store.Close()

			if input.SessionID == "" {
				input.SessionID = uuid.New().String()
			}
			if input.UserID == "" {
				input.UserID = "local:prit"
			}
			if input.Channel == "" {
				input.Channel = gateway.ClientTypeCLI
			}

			stream <- engine.StreamEvent{
				Type:      "STATUS_UPDATE",
				AgentName: "SQLiteStore",
				Payload:   fmt.Sprintf("Querying session %s...", input.SessionID),
			}

			sess, err := store.GetOrCreateSession(ctx, input.SessionID, input.UserID, input.Channel)
			if err != nil {
				engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
					Level:   "ERROR",
					Source:  "sqlite_store",
					Message: fmt.Sprintf("Failed GetOrCreateSession: %v", err),
				})
				return nil, err
			}

			engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
				Level:   "INFO",
				Source:  "sqlite_store",
				Message: fmt.Sprintf("Session ready: id=%s user=%s channel=%s", sess.SessionID, sess.UserID, sess.Channel),
			})

			return sess, nil
		},
	})

	// 2. AppendMessage
	r.Register(engine.Module{
		ID:          "l2_session_store_append_message",
		Name:        "Layer 2: Session Store (AppendMessage)",
		Category:    "Isolated Module",
		Description: "Appends a new turn message directly to the SQLite conversation store.",
		InputType:   reflect.TypeOf(AppendMessageInput{}),
		Presets: []engine.Preset{
			{
				ID:       "user_message",
				Name:     "Append User Message",
				Category: "Happy Path",
				Payload: AppendMessageInput{
					SessionID: "bench-demo-session",
					TurnID:    uuid.New().String(),
					Role:      "user",
					AgentName: "User",
					Content:   "Analyze latest benchmark results",
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var input AppendMessageInput
			if err := json.Unmarshal(inputRaw, &input); err != nil {
				return nil, err
			}

			store, err := getWorkbenchStore()
			if err != nil {
				return nil, err
			}
			defer store.Close()

			msg := session.ChatMessage{
				SessionID: input.SessionID,
				TurnID:    input.TurnID,
				Role:      input.Role,
				AgentName: input.AgentName,
				Content:   input.Content,
				CreatedAt: time.Now().UTC(),
			}

			if err := store.AppendMessage(ctx, msg); err != nil {
				return nil, err
			}

			stream <- engine.StreamEvent{
				Type:      "STATUS_UPDATE",
				AgentName: "SQLiteStore",
				Payload:   fmt.Sprintf("Appended message into session %s", input.SessionID),
			}

			return map[string]any{
				"status":  "MESSAGE_APPENDED",
				"message": msg,
			}, nil
		},
	})

	// 3. GetSessionHistory
	r.Register(engine.Module{
		ID:          "l2_session_store_get_history",
		Name:        "Layer 2: Session Store (GetSessionHistory)",
		Category:    "Isolated Module",
		Description: "Retrieves chronological message history for a given session from SQLite.",
		InputType:   reflect.TypeOf(GetSessionHistoryInput{}),
		Presets: []engine.Preset{
			{
				ID:       "get_history",
				Name:     "Fetch Recent 10 Messages",
				Category: "Happy Path",
				Payload: GetSessionHistoryInput{
					SessionID: "bench-demo-session",
					Limit:     10,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var input GetSessionHistoryInput
			if err := json.Unmarshal(inputRaw, &input); err != nil {
				return nil, err
			}

			store, err := getWorkbenchStore()
			if err != nil {
				return nil, err
			}
			defer store.Close()

			limit := input.Limit
			if limit <= 0 {
				limit = 20
			}

			stream <- engine.StreamEvent{
				Type:      "STATUS_UPDATE",
				AgentName: "SQLiteStore",
				Payload:   fmt.Sprintf("Reading up to %d messages for session %s", limit, input.SessionID),
			}

			history, err := store.GetSessionHistory(ctx, input.SessionID, limit)
			if err != nil {
				return nil, err
			}

			return map[string]any{
				"session_id":    input.SessionID,
				"message_count": len(history),
				"messages":      history,
			}, nil
		},
	})
}

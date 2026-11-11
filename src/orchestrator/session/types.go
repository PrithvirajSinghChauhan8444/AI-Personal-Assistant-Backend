package session

import (
	"time"

	"assistant/src/gateway"
)

// Session represents a persistent conversation thread.
type Session struct {
	SessionID string             `json:"session_id"`
	UserID    string             `json:"user_id"`
	Channel   gateway.ClientType `json:"channel"`
	CreatedAt time.Time          `json:"created_at"`
	UpdatedAt time.Time          `json:"updated_at"`
}

// ChatMessage represents a single message recorded in the turn history.
type ChatMessage struct {
	ID            int64     `json:"id,omitempty"`
	SessionID     string    `json:"session_id"`
	TurnID        string    `json:"turn_id"`
	Role          string    `json:"role"`           // "user", "assistant", "system", "tool"
	AgentName     string    `json:"agent_name"`     // e.g. "manager", "system", "browser"
	Content       string    `json:"content"`
	ToolCallsJSON string    `json:"tool_calls_json,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
}

// CheckpointStatus represents the approval state of a paused turn.
type CheckpointStatus string

const (
	CheckpointPendingApproval CheckpointStatus = "PENDING_APPROVAL"
	CheckpointResumed         CheckpointStatus = "RESUMED"
	CheckpointCancelled       CheckpointStatus = "CANCELLED"
)

// Checkpoint represents serialized turn state paused for human-in-the-loop review.
type Checkpoint struct {
	RequestID       string              `json:"request_id"`
	SessionID       string              `json:"session_id"`
	Status          CheckpointStatus    `json:"status"`
	TriggerType     gateway.TriggerType `json:"trigger_type"`
	TargetAgent     string              `json:"target_agent"`
	PendingToolName string              `json:"pending_tool_name"`
	PendingToolArgs string              `json:"pending_tool_args"`
	TurnStateJSON   string              `json:"turn_state_json"`
	CreatedAt       time.Time           `json:"created_at"`
	UpdatedAt       time.Time           `json:"updated_at"`
}

// ToolAuditEntry records a security and execution telemetry trail for every tool invocation.
type ToolAuditEntry struct {
	ID         int64     `json:"id,omitempty"`
	SessionID  string    `json:"session_id"`
	TurnID     string    `json:"turn_id"`
	ToolName   string    `json:"tool_name"`
	RiskLevel  string    `json:"risk_level"`
	Status     string    `json:"status"` // "SUCCESS", "FAILED", "HITL_APPROVED", "HITL_REJECTED"
	DurationMs int64     `json:"duration_ms"`
	CreatedAt  time.Time `json:"created_at"`
}

// ActiveState encapsulates the loaded session and relevant historical context for a turn.
type ActiveState struct {
	SessionID   string
	UserID      string
	Channel     gateway.ClientType
	Trigger     gateway.TriggerType
	AllowedCaps []string
	History     []ChatMessage
}

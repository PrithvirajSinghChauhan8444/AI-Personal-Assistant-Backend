package protocol

import (
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
)

// FrameType identifies the wire protocol discriminator for NDJSON messages.
type FrameType string

const (
	// Handshake
	FrameTypeReady FrameType = "ready"

	// Control Plane -> Cognitive Plane (Go -> Python)
	FrameTypeStartTurn  FrameType = "start_turn"
	FrameTypeToolResult FrameType = "tool_result"
	FrameTypeCancelTurn FrameType = "cancel_turn"

	// Cognitive Plane -> Control Plane (Python -> Go)
	FrameTypeAgentThought    FrameType = "agent_thought"
	FrameTypeToolCall        FrameType = "tool_call"
	FrameTypeToken           FrameType = "token"
	FrameTypeTurnComplete    FrameType = "turn_complete"
	FrameTypeAutonomousEvent FrameType = "autonomous_event"

	// Bidirectional Diagnostic
	FrameTypeError FrameType = "error"
)

// MasterFrame defines the standard wire envelope for all NDJSON frames.
type MasterFrame struct {
	FrameID     string          `json:"frame_id"`
	SessionID   string          `json:"session_id"`
	TurnID      string          `json:"turn_id"`
	TimestampMs int64           `json:"timestamp_ms"`
	Type        FrameType       `json:"type"`
	Payload     json.RawMessage `json:"payload"`
}

// ReadyPayload carries daemon initial status upon startup.
type ReadyPayload struct {
	Status          string   `json:"status"`
	Version         string   `json:"version,omitempty"`
	SupportedAgents []string `json:"supported_agents,omitempty"`
}

// ChatMessage represents a single message in the conversation history.
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
	Name    string `json:"name,omitempty"`
}

// ToolManifest defines a tool capability schema passed to the model.
type ToolManifest struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Parameters  map[string]any `json:"parameters"`
}

// StartTurnPayload initiates a reasoning turn in Python.
type StartTurnPayload struct {
	TargetAgent string         `json:"target_agent"`
	Prompt      string         `json:"prompt"`
	Messages    []ChatMessage  `json:"messages"`
	Context     map[string]any `json:"context,omitempty"`
	Tools       []ToolManifest `json:"tools,omitempty"`
}

// AgentThoughtPayload carries internal agent reasoning tokens or steps.
type AgentThoughtPayload struct {
	Thought   string `json:"thought"`
	AgentName string `json:"agent_name,omitempty"`
}

// ToolCallPayload requests execution of a native tool by Go Layer 3.
type ToolCallPayload struct {
	CallID         string         `json:"call_id"`
	IdempotencyKey string         `json:"idempotency_key,omitempty"`
	ToolName       string         `json:"tool_name"`
	Arguments      map[string]any `json:"arguments"`
}

// ToolResultPayload delivers execution outputs from Go Layer 3 back to Python.
type ToolResultPayload struct {
	CallID       string `json:"call_id"`
	ToolName     string `json:"tool_name,omitempty"`
	ExitCode     int    `json:"exit_code"`
	Output       string `json:"output"`
	ArtifactPath string `json:"artifact_path,omitempty"`
	DurationMs   int64  `json:"duration_ms"`
	IsError      bool   `json:"is_error,omitempty"`
}

// TokenPayload emits real-time streamed text deltas to the user.
type TokenPayload struct {
	Delta     string `json:"delta"`
	AgentName string `json:"agent_name,omitempty"`
}

// TokenUsage tracks token expenditure across a turn.
type TokenUsage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// TurnCompletePayload marks the conclusion of an agent reasoning turn.
type TurnCompletePayload struct {
	Status        string      `json:"status"`
	FinalResponse string      `json:"final_response,omitempty"`
	Usage         TokenUsage  `json:"usage"`
}

// AutonomousEventPayload represents an unsolicited background event.
type AutonomousEventPayload struct {
	Source    string         `json:"source"`
	EventType string         `json:"event_type"`
	Summary   string         `json:"summary"`
	RawData   map[string]any `json:"raw_data,omitempty"`
}

// CancelTurnPayload requests immediate abort of an in-flight turn.
type CancelTurnPayload struct {
	Reason string `json:"reason"`
}

// ErrorPayload describes a protocol or runtime exception.
type ErrorPayload struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Details string `json:"details,omitempty"`
}

// Validation errors.
var (
	ErrEmptyFrameID   = errors.New("frame_id cannot be empty")
	ErrEmptyTurnID    = errors.New("turn_id cannot be empty")
	ErrEmptyFrameType = errors.New("frame type cannot be empty")
	ErrNilPayload     = errors.New("frame payload cannot be nil")
)

// Validate checks essential envelope invariants.
func (f *MasterFrame) Validate() error {
	if f.FrameID == "" {
		return ErrEmptyFrameID
	}
	if f.TurnID == "" && f.Type != FrameTypeReady {
		return ErrEmptyTurnID
	}
	if f.Type == "" {
		return ErrEmptyFrameType
	}
	if len(f.Payload) == 0 {
		return ErrNilPayload
	}
	return nil
}

// UnmarshalPayload deserializes the raw payload into a destination struct.
func (f *MasterFrame) UnmarshalPayload(dest any) error {
	if len(f.Payload) == 0 {
		return ErrNilPayload
	}
	if err := json.Unmarshal(f.Payload, dest); err != nil {
		return fmt.Errorf("failed to unmarshal payload for type %s: %w", f.Type, err)
	}
	return nil
}

// NewMasterFrame constructs a validated MasterFrame with a generated UUID and current timestamp.
func NewMasterFrame(sessionID, turnID string, frameType FrameType, payload any) (*MasterFrame, error) {
	raw, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal frame payload: %w", err)
	}

	frame := &MasterFrame{
		FrameID:     "frm_" + uuid.New().String(),
		SessionID:   sessionID,
		TurnID:      turnID,
		TimestampMs: time.Now().UnixMilli(),
		Type:        frameType,
		Payload:     raw,
	}

	if err := frame.Validate(); err != nil {
		return nil, err
	}
	return frame, nil
}

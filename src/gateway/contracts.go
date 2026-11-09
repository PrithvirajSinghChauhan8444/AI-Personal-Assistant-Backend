package gateway

import "time"

// ClientType defines the ingress channel for client requests.
type ClientType string

const (
	ClientTypeCLI      ClientType = "CLI"
	ClientTypeTelegram ClientType = "TELEGRAM"
	ClientTypeWeb      ClientType = "WEB"
	ClientTypeInternal ClientType = "INTERNAL" // Background watchers (Gmail daemon, cron)
)

// TriggerType defines execution context (human present vs automated background process).
type TriggerType string

const (
	TriggerInteractive TriggerType = "INTERACTIVE" // Human user at terminal or browser
	TriggerAutonomous  TriggerType = "AUTONOMOUS"  // Background watcher or daemon
)

// InboundTurnRequest is the normalized struct passed from Layer 1 to Layer 2.
type InboundTurnRequest struct {
	// Identity & Session Conduit
	SessionID string      `json:"session_id"` // Client session UUID (empty if new session)
	UserID    string      `json:"user_id"`    // e.g., "local:prit"
	Channel   ClientType  `json:"channel"`    // CLI, WEB, TELEGRAM, or INTERNAL
	Trigger   TriggerType `json:"trigger"`    // INTERACTIVE vs AUTONOMOUS

	// Security & Authorization Scope
	AllowedCapabilities []string `json:"allowed_capabilities"` // In autonomous mode, restricts tool scope

	// Direct Agent Addressing
	TargetAgent string `json:"target_agent"` // "auto" (routed by Orchestrator), or explicit: "system", "browser", "research"

	// Telemetry & Tracing
	TraceID    string    `json:"trace_id"`
	SpanID     string    `json:"span_id"`
	ReceivedAt time.Time `json:"received_at"`

	// Content
	Prompt string `json:"prompt"` // Cleaned user prompt (stripped of @agent prefix)
}

// EventType defines streaming event categories sent back to Layer 1.
type EventType string

const (
	EventTokenChunk   EventType = "TOKEN_CHUNK"   // Text to display live
	EventThoughtChunk EventType = "THOUGHT_CHUNK" // Agent reasoning or internal monologue
	EventStatusUpdate EventType = "STATUS_UPDATE" // Operational status (e.g. "Running tool...")
	EventHITLRequest  EventType = "HITL_REQUEST"  // Interactive human approval prompt
	EventTurnComplete EventType = "TURN_COMPLETE" // Final completion
	EventTurnError    EventType = "TURN_ERROR"    // Failure event
)

// OutboundEvent is streamed from Layer 2 back to Layer 1 for live rendering.
type OutboundEvent struct {
	SessionID string    `json:"session_id"`
	TraceID   string    `json:"trace_id"`
	Type      EventType `json:"type"`

	// Agent Attribution (User always knows WHO is acting or speaking)
	AgentName string `json:"agent_name"` // "Orchestrator", "SystemAgent", "BrowserAgent", etc.

	// Payload Fields (populated based on Type)
	TextDelta string              `json:"text_delta,omitempty"` // For tokens and thoughts
	StatusMsg string              `json:"status_msg,omitempty"` // For status updates
	HITL      *HITLApprovalPrompt `json:"hitl,omitempty"`       // For approval requests
	Metrics   *TurnMetrics        `json:"metrics,omitempty"`    // For turn completion
	Error     string              `json:"error,omitempty"`      // For errors
}

// HITLApprovalPrompt is sent when human approval is required before executing a high-risk tool.
type HITLApprovalPrompt struct {
	RequestID        string   `json:"request_id"`
	ToolName         string   `json:"tool_name"`
	Reason           string   `json:"reason"`
	ArgumentsJSON    string   `json:"arguments_json"`
	AvailableChoices []string `json:"available_choices"` // e.g. ["Approve", "Deny"]
}

// HITLResponse is captured by Layer 1 when user approves or denies an action.
type HITLResponse struct {
	RequestID    string    `json:"request_id"`
	SessionID    string    `json:"session_id"`
	Approved     bool      `json:"approved"`
	UserFeedback string    `json:"user_feedback,omitempty"` // Optional modification or rationale
	RespondedAt  time.Time `json:"responded_at"`
}

// TurnMetrics reports token and latency telemetry upon turn completion.
type TurnMetrics struct {
	ModelName         string `json:"model_name"`
	PromptTokens      int32  `json:"prompt_tokens"`
	CompletionTokens  int32  `json:"completion_tokens"`
	CachedTokens      int32  `json:"cached_tokens"`
	TimeToFirstByteMs int64  `json:"ttft_ms"`
	TotalDurationMs   int64  `json:"total_duration_ms"`
}

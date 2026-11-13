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

// ExecutionPhase represents the active operational stage of the cognitive core.
type ExecutionPhase string

const (
	PhaseIdle            ExecutionPhase = "IDLE"
	PhasePlanning        ExecutionPhase = "PLANNING"
	PhaseExecuting       ExecutionPhase = "EXECUTING"
	PhaseWaitingApproval ExecutionPhase = "WAITING_APPROVAL"
	PhaseCompleted       ExecutionPhase = "COMPLETED"
	PhaseFailed          ExecutionPhase = "FAILED"
)

// EventType defines streaming event categories sent back to Layer 1.
type EventType string

const (
	EventTokenChunk      EventType = "TOKEN_CHUNK"      // Text to display live
	EventThoughtChunk    EventType = "THOUGHT_CHUNK"    // Agent reasoning or internal monologue
	EventThoughtComplete EventType = "THOUGHT_COMPLETE" // Thought reasoning concluded; action/answer begun
	EventStatusUpdate    EventType = "STATUS_UPDATE"    // Operational status (e.g. "Running tool...")
	EventPhaseChange     EventType = "PHASE_CHANGE"     // Core execution phase transition
	EventPlanCreated     EventType = "PLAN_CREATED"     // Decomposed DAG plan emitted by planner
	EventPlanDiagnostic  EventType = "PLAN_DIAGNOSTIC"  // Planning failure or fallback diagnostic
	EventSubtaskStart    EventType = "SUBTASK_START"    // Subtask execution initiation
	EventSubtaskProgress EventType = "SUBTASK_PROGRESS" // Subtask lifecycle progress update
	EventSubtaskComplete EventType = "SUBTASK_COMPLETE" // Subtask finished successfully
	EventSubtaskFailed   EventType = "SUBTASK_FAILED"   // Subtask execution failed
	EventToolCall        EventType = "TOOL_CALL"        // Tool execution start
	EventToolResult      EventType = "TOOL_RESULT"      // Tool execution result
	EventSystemLog       EventType = "SYSTEM_LOG"       // Live operational log entry
	EventHITLRequest     EventType = "HITL_REQUEST"     // Interactive human approval prompt
	EventTurnComplete    EventType = "TURN_COMPLETE"    // Final completion
	EventTurnError       EventType = "TURN_ERROR"       // Failure event
)

// LogSeverity defines log level categories for operational diagnostics.
type LogSeverity string

const (
	LogSeverityDebug LogSeverity = "DEBUG"
	LogSeverityInfo  LogSeverity = "INFO"
	LogSeverityWarn  LogSeverity = "WARN"
	LogSeverityError LogSeverity = "ERROR"
)

// LogEntry encapsulates a structured operational log item.
type LogEntry struct {
	Timestamp time.Time   `json:"timestamp"`
	Severity  LogSeverity `json:"severity"`
	Component string      `json:"component"`
	Message   string      `json:"message"`
	TurnID    string      `json:"turn_id,omitempty"`
}

// SubtaskItemInfo represents an individual subtask specification within a DAG plan.
type SubtaskItemInfo struct {
	ID               string                 `json:"id"`
	Description      string                 `json:"description"`
	AssignedWorker   string                 `json:"assigned_worker"`
	DependsOn        []string               `json:"depends_on"`
	Status           string                 `json:"status"` // PENDING, IN_PROGRESS, COMPLETED, FAILED
	ConfidenceScore  float64                `json:"confidence_score,omitempty"`
	ConfidenceReason string                 `json:"confidence_reason,omitempty"`
	InputContext     map[string]interface{} `json:"input_context,omitempty"`
	Output           string                 `json:"output,omitempty"`
	Error            string                 `json:"error,omitempty"`
	ArtifactPath     string                 `json:"artifact_path,omitempty"`
	DurationMs       int64                  `json:"duration_ms,omitempty"`
}

// PlanInfo encapsulates a decomposed execution plan DAG.
type PlanInfo struct {
	PlanID      string            `json:"plan_id,omitempty"`
	PrimaryGoal string            `json:"primary_goal"`
	SubTasks    []SubtaskItemInfo `json:"subtasks"`
}

// PlanDiagnosticInfo provides root cause telemetry when planning fails or falls back.
type PlanDiagnosticInfo struct {
	Goal              string `json:"goal"`
	Reason            string `json:"reason"`
	FallbackTriggered bool   `json:"fallback_triggered"`
	Error             string `json:"error,omitempty"`
}

// SubtaskEventInfo encapsulates detailed telemetry for subtask lifecycle events.
type SubtaskEventInfo struct {
	SubtaskID    string                 `json:"subtask_id"`
	Worker       string                 `json:"worker"`
	Description  string                 `json:"description"`
	Status       string                 `json:"status"`
	DependsOn    []string               `json:"depends_on,omitempty"`
	InputPrompt  string                 `json:"input_prompt,omitempty"`
	InputContext map[string]interface{} `json:"input_context,omitempty"`
	Output       string                 `json:"output,omitempty"`
	ArtifactPath string                 `json:"artifact_path,omitempty"`
	DurationMs   int64                  `json:"duration_ms,omitempty"`
	Error        string                 `json:"error,omitempty"`
}

// ActiveActionInfo describes a tool or subtask currently running in-flight.
type ActiveActionInfo struct {
	Type      string         `json:"type"` // "TOOL" or "SUBTASK"
	Name      string         `json:"name"` // Tool name or worker agent
	CallID    string         `json:"call_id,omitempty"`
	SubtaskID string         `json:"subtask_id,omitempty"`
	Arguments map[string]any `json:"arguments,omitempty"`
	StartedAt time.Time      `json:"started_at"`
	ElapsedMs int64          `json:"elapsed_ms"`
}

// TurnSnapshot provides a complete, point-in-time snapshot of the execution state.
type TurnSnapshot struct {
	SessionID      string              `json:"session_id"`
	TurnID         string              `json:"turn_id"`
	TraceID        string              `json:"trace_id"`
	Phase          ExecutionPhase      `json:"phase"`
	ActiveAgent    string              `json:"active_agent"`
	ActiveAction   *ActiveActionInfo   `json:"active_action,omitempty"`
	Plan           *PlanInfo           `json:"plan,omitempty"`
	Subtasks       []SubtaskItemInfo   `json:"subtasks,omitempty"`
	PendingHITL    *HITLApprovalPrompt `json:"pending_hitl,omitempty"`
	ThoughtsBuffer string              `json:"thoughts_buffer,omitempty"`
	AnswerBuffer   string              `json:"answer_buffer,omitempty"`
	RecentLogs     []LogEntry          `json:"recent_logs,omitempty"`
	StartedAt      time.Time           `json:"started_at"`
	UpdatedAt      time.Time           `json:"updated_at"`
}

// ToolCallInfo provides structured details when an agent invokes a tool.
type ToolCallInfo struct {
	CallID         string         `json:"call_id"`
	ToolName       string         `json:"tool_name"`
	Arguments      map[string]any `json:"arguments,omitempty"`
	ArgsJSON       string         `json:"args_json,omitempty"`
	IdempotencyKey string         `json:"idempotency_key,omitempty"`
}

// ToolResultInfo provides structured details when a tool execution finishes.
type ToolResultInfo struct {
	CallID       string `json:"call_id"`
	ToolName     string `json:"tool_name,omitempty"`
	ExitCode     int    `json:"exit_code"`
	Output       string `json:"output,omitempty"`
	ArtifactPath string `json:"artifact_path,omitempty"`
	DurationMs   int64  `json:"duration_ms"`
	IsError      bool   `json:"is_error"`
}

// OutboundEvent is streamed from Layer 2 back to Layer 1 for live rendering.
type OutboundEvent struct {
	SessionID string         `json:"session_id"`
	TurnID    string         `json:"turn_id,omitempty"`
	TraceID   string         `json:"trace_id"`
	Type      EventType      `json:"type"`
	Phase     ExecutionPhase `json:"phase,omitempty"`
	Timestamp time.Time      `json:"timestamp"`

	// Agent Attribution (User always knows WHO is acting or speaking)
	AgentName string `json:"agent_name"` // "Orchestrator", "SystemAgent", "BrowserAgent", etc.

	// Payload Fields (populated based on Type)
	TextDelta string              `json:"text_delta,omitempty"` // For tokens and thoughts
	StatusMsg string              `json:"status_msg,omitempty"` // For status updates
	HITL      *HITLApprovalPrompt `json:"hitl,omitempty"`       // For approval requests
	Metrics   *TurnMetrics        `json:"metrics,omitempty"`    // For turn completion
	Error     string              `json:"error,omitempty"`      // For errors

	// Tool execution fields
	ToolCall   *ToolCallInfo   `json:"tool_call,omitempty"`   // Populated when Type == EventToolCall
	ToolResult *ToolResultInfo `json:"tool_result,omitempty"` // Populated when Type == EventToolResult

	// Observer Lifecycle & Telemetry Fields
	Plan       *PlanInfo           `json:"plan,omitempty"`       // Populated when Type == EventPlanCreated
	Diagnostic *PlanDiagnosticInfo `json:"diagnostic,omitempty"` // Populated when Type == EventPlanDiagnostic
	Subtask    *SubtaskEventInfo   `json:"subtask,omitempty"`    // Populated for Subtask events
	Log        *LogEntry           `json:"log,omitempty"`        // Populated when Type == EventSystemLog
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

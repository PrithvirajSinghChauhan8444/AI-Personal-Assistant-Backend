package engine

import (
	"context"
	"encoding/json"
	"reflect"
	"time"
)

// FieldSchema describes a single parameter field discovered via reflection.
type FieldSchema struct {
	Name        string        `json:"name"`
	Type        string        `json:"type"`
	Required    bool          `json:"required"`
	Description string        `json:"description,omitempty"`
	Enum        []string      `json:"enum,omitempty"`
	Default     any           `json:"default,omitempty"`
	Fields      []FieldSchema `json:"fields,omitempty"`
}

// ModuleSchema encapsulates the input contract of a registered module.
type ModuleSchema struct {
	TypeName string        `json:"type_name"`
	Fields   []FieldSchema `json:"fields"`
}

// Preset is a pre-configured input test case for quick execution.
type Preset struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Category    string `json:"category"` // "Happy Path", "Security", "Edge Case", "HITL"
	Description string `json:"description"`
	Payload     any    `json:"payload"`
}

// StreamEvent represents an unadulterated live telemetry event emitted during execution.
type StreamEvent struct {
	Index     int       `json:"index"`
	Timestamp time.Time `json:"timestamp"`
	Type      string    `json:"type"`
	AgentName string    `json:"agent_name,omitempty"`
	Payload   any       `json:"payload,omitempty"`
	Raw       string    `json:"raw,omitempty"`
}

// ExecutionRecord stores the complete ground truth of an execution run on disk.
type ExecutionRecord struct {
	ID                string            `json:"id"`
	ModuleID          string            `json:"module_id"`
	ModuleName        string            `json:"module_name"`
	Category          string            `json:"category"`
	StartedAt         time.Time         `json:"started_at"`
	CompletedAt       time.Time         `json:"completed_at"`
	DurationUs        int64             `json:"duration_us"`
	DurationFormatted string            `json:"duration_formatted"`
	Input             json.RawMessage   `json:"input"`
	Events            []StreamEvent     `json:"events"`
	Logs              []GoLogEntry      `json:"logs,omitempty"`
	Telemetry         *RuntimeTelemetry `json:"telemetry,omitempty"`
	Output            any               `json:"output,omitempty"`
	Error             *string           `json:"error,omitempty"`
	Panic             *string           `json:"panic,omitempty"`
	Aborted           bool              `json:"aborted"`
	Status            string            `json:"status"` // "SUCCESS", "ERROR", "PANIC", "ABORTED"
}

// ModuleExecutionFunc defines the agnostic runner contract for any module or pipeline.
type ModuleExecutionFunc func(ctx context.Context, inputRaw json.RawMessage, stream chan<- StreamEvent) (output any, err error)

// Module represents a fully registered module in the workbench.
type Module struct {
	ID          string              `json:"id"`
	Name        string              `json:"name"`
	Category    string              `json:"category"` // "Isolated Module" | "Pipeline"
	Description string              `json:"description"`
	InputType   reflect.Type        `json:"-"`
	Schema      ModuleSchema        `json:"schema"`
	Presets     []Preset            `json:"presets"`
	Execute     ModuleExecutionFunc `json:"-"`
}

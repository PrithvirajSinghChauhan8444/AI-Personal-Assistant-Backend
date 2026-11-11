package tools

import (
	"context"
)

// RiskLevel defines the risk tier of a tool, driving HITL gates and execution permissions.
type RiskLevel string

const (
	// RiskLow represents read-only operations with no destructive side effects.
	RiskLow RiskLevel = "LOW"

	// RiskMedium represents non-destructive mutations (e.g. writing workspace files, creating drafts).
	RiskMedium RiskLevel = "MEDIUM"

	// RiskHigh represents critical mutations or OS commands requiring explicit authorization.
	RiskHigh RiskLevel = "HIGH"
)

// ToolMetadata encapsulates the cognitive contract exposed to agents and language models.
type ToolMetadata struct {
	Name               string    `json:"name"`
	Category           string    `json:"category"`
	Description        string    `json:"description"`
	ParameterSchema    string    `json:"parameter_schema"`
	PromptUsageTip     string    `json:"prompt_usage_tip"`
	Risk               RiskLevel `json:"risk"`
	RequiredCapability string    `json:"required_capability"`
}

// ToolResult standardizes execution outputs across all native and external tools.
type ToolResult struct {
	CallID       string `json:"call_id"`
	Stdout       string `json:"stdout"`
	Stderr       string `json:"stderr,omitempty"`
	ExitCode     int    `json:"exit_code"`
	IsError      bool   `json:"is_error"`
	DurationMs   int64  `json:"duration_ms"`
	ArtifactPath string `json:"artifact_path,omitempty"`
}

// Tool represents a self-describing, natively executable capability.
type Tool interface {
	Metadata() ToolMetadata
	Execute(ctx context.Context, argsJSON string) (*ToolResult, error)
}

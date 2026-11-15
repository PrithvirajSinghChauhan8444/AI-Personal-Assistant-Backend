package orchestrator

import (
	"assistant/src/orchestrator/planner"
)

// CheckpointTurnState represents the full serializable state of a turn paused for approval.
type CheckpointTurnState struct {
	SessionID        string            `json:"session_id"`
	TurnID           string            `json:"turn_id"`
	SubtaskID        string            `json:"subtask_id"`
	ToolName         string            `json:"tool_name"`
	ArgsJSON         string            `json:"args_json"`
	Plan             *planner.TaskPlan `json:"plan"`
	CompletedOutputs map[string]string `json:"completed_outputs"`
	TurnContext      *TurnContext      `json:"turn_context"`
}

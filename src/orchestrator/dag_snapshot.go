package orchestrator

import (
	"errors"
)

var (
	// ErrNoActiveDAG is returned when a session has no currently executing DAG.
	ErrNoActiveDAG = errors.New("no active DAG found for session")
)

// InFlightTaskSnapshot captures the live execution status of an active subtask.
type InFlightTaskSnapshot struct {
	SubtaskID    string                 `json:"subtask_id"`
	Worker       string                 `json:"worker"`
	ElapsedMs    int64                  `json:"elapsed_ms"`
	InputContext map[string]interface{} `json:"input_context,omitempty"`
}

// DAGExecutionSnapshot represents a point-in-time state of the topological execution graph.
type DAGExecutionSnapshot struct {
	PlanID         string                 `json:"plan_id"`
	PrimaryGoal    string                 `json:"primary_goal"`
	TotalTasks     int                    `json:"total_tasks"`
	CompletedTasks int                    `json:"completed_tasks"`
	FailedTasks    int                    `json:"failed_tasks"`
	InFlightTasks  []InFlightTaskSnapshot `json:"in_flight_tasks"`
	PendingTasks   []string               `json:"pending_tasks"`
	DependencyTree map[string][]string    `json:"dependency_tree"`
}

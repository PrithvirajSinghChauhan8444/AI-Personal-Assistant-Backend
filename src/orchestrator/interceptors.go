package orchestrator

import (
	"context"

	"assistant/src/orchestrator/planner"
)

// SubtaskResult encapsulates execution outputs for interceptor hooks.
type SubtaskResult struct {
	Output       string
	ArtifactPath string
	DurationMs   int64
	Error        error
}

// TaskInterceptor defines modular pre- and post-execution hooks for subtasks.
type TaskInterceptor interface {
	BeforeSubtask(ctx context.Context, task *planner.SubTask) error
	AfterSubtask(ctx context.Context, task *planner.SubTask, result *SubtaskResult)
}

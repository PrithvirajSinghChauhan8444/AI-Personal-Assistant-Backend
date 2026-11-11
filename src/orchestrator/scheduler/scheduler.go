package scheduler

import (
	"errors"
	"fmt"
	"sync"

	"assistant/src/orchestrator/planner"
)

var (
	// ErrTaskNotFound is returned when operating on a non-existent subtask ID.
	ErrTaskNotFound = errors.New("subtask id not found in plan")
)

// TaskScheduler walks the TaskPlan DAG, determines ready tasks, and enforces concurrency limits.
type TaskScheduler struct {
	mu                 sync.RWMutex
	plan               *planner.TaskPlan
	allowParallel      bool
	maxParallel        int
	autoHealDeadlocks  bool
}

// Config holds configuration parameters for the TaskScheduler.
type Config struct {
	AllowParallel     bool
	MaxParallel       int
	AutoHealDeadlocks bool
}

// NewTaskScheduler initializes a scheduler with the provided TaskPlan.
func NewTaskScheduler(plan *planner.TaskPlan, cfg Config) *TaskScheduler {
	if cfg.MaxParallel <= 0 {
		cfg.MaxParallel = 4
	}
	return &TaskScheduler{
		plan:              plan,
		allowParallel:     cfg.AllowParallel,
		maxParallel:       cfg.MaxParallel,
		autoHealDeadlocks: cfg.AutoHealDeadlocks,
	}
}

// GetExecutableTasks returns the next batch of subtasks ready for execution.
func (s *TaskScheduler) GetExecutableTasks() []*planner.SubTask {
	s.mu.Lock()
	defer s.mu.Unlock()

	completedIDs := make(map[string]bool)
	var pendingTasks []*planner.SubTask
	var inProgressTasks []*planner.SubTask

	for i := range s.plan.SubTasks {
		st := &s.plan.SubTasks[i]
		switch st.Status {
		case planner.StatusCompleted:
			completedIDs[st.ID] = true
		case planner.StatusPending:
			pendingTasks = append(pendingTasks, st)
		case planner.StatusInProgress:
			inProgressTasks = append(inProgressTasks, st)
		}
	}

	if len(pendingTasks) == 0 {
		return nil
	}

	var readyTasks []*planner.SubTask
	for _, st := range pendingTasks {
		if s.areDependenciesMet(st, completedIDs) {
			readyTasks = append(readyTasks, st)
		}
	}

	// Deadlock check: pending tasks exist, but none ready and none currently in progress
	if len(readyTasks) == 0 && len(inProgressTasks) == 0 && s.autoHealDeadlocks {
		s.autoHealPending(pendingTasks)
		return nil
	}

	return s.selectDispatchableTasks(readyTasks)
}

func (s *TaskScheduler) areDependenciesMet(st *planner.SubTask, completed map[string]bool) bool {
	for _, depID := range st.DependsOn {
		if !completed[depID] {
			return false
		}
	}
	return true
}

func (s *TaskScheduler) selectDispatchableTasks(ready []*planner.SubTask) []*planner.SubTask {
	var toDispatch []*planner.SubTask
	agentsSeen := make(map[string]bool)

	for _, st := range ready {
		worker := st.GetWorker()
		if !agentsSeen[worker] {
			agentsSeen[worker] = true
			toDispatch = append(toDispatch, st)
			if !s.allowParallel || len(toDispatch) >= s.maxParallel {
				break
			}
		}
	}
	return toDispatch
}

// GetDependencyOutputs returns outputs of all completed dependencies for the given task.
func (s *TaskScheduler) GetDependencyOutputs(taskID string) map[string]string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	task := s.findTask(taskID)
	if task == nil || len(task.DependsOn) == 0 {
		return nil
	}

	outputs := make(map[string]string)
	for _, depID := range task.DependsOn {
		depTask := s.findTask(depID)
		if depTask != nil && depTask.Status == planner.StatusCompleted && depTask.Output != "" {
			outputs[depID] = depTask.Output
		}
	}
	return outputs
}

// MarkInProgress transitions a task to IN_PROGRESS.
func (s *TaskScheduler) MarkInProgress(taskID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	task := s.findTask(taskID)
	if task == nil {
		return ErrTaskNotFound
	}
	task.Status = planner.StatusInProgress
	return nil
}

// MarkCompleted records output and transitions a task to COMPLETED.
func (s *TaskScheduler) MarkCompleted(taskID string, output string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	task := s.findTask(taskID)
	if task == nil {
		return ErrTaskNotFound
	}
	task.Status = planner.StatusCompleted
	task.Output = output
	return nil
}

// MarkFailed records an error and transitions a task to FAILED.
func (s *TaskScheduler) MarkFailed(taskID string, errMsg string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	task := s.findTask(taskID)
	if task == nil {
		return ErrTaskNotFound
	}
	task.Status = planner.StatusFailed
	task.Error = errMsg
	return nil
}

// IsComplete returns true when all subtasks have terminated.
func (s *TaskScheduler) IsComplete() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	for _, st := range s.plan.SubTasks {
		if st.Status == planner.StatusPending || st.Status == planner.StatusInProgress {
			return false
		}
	}
	return true
}

// GetPlan returns the current state of the TaskPlan.
func (s *TaskScheduler) GetPlan() *planner.TaskPlan {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.plan
}

func (s *TaskScheduler) findTask(taskID string) *planner.SubTask {
	for i := range s.plan.SubTasks {
		if s.plan.SubTasks[i].ID == taskID {
			return &s.plan.SubTasks[i]
		}
	}
	return nil
}

func (s *TaskScheduler) autoHealPending(pending []*planner.SubTask) {
	for _, st := range pending {
		st.Status = planner.StatusAborted
		st.Error = fmt.Sprintf("Dependency blocked / deadlock detected for task %q", st.ID)
	}
}

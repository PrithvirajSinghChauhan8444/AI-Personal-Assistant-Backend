package sys

import (
	"sync"
	"time"
)

// TrackedProcess represents a running or finished background process.
type TrackedProcess struct {
	PID       int       `json:"pid"`
	Command   string    `json:"command"`
	StartTime time.Time `json:"start_time"`
	LogPath   string    `json:"log_path"`
	Status    string    `json:"status"` // "running" or "exited"
	ExitCode  int       `json:"exit_code"`
}

// ProcessRegistry manages background processes safely across concurrent routines.
type ProcessRegistry struct {
	mu        sync.RWMutex
	processes map[int]*TrackedProcess
}

// GlobalProcessRegistry is the shared process registry instance.
var GlobalProcessRegistry = NewProcessRegistry()

// NewProcessRegistry creates an initialized ProcessRegistry.
func NewProcessRegistry() *ProcessRegistry {
	return &ProcessRegistry{
		processes: make(map[int]*TrackedProcess),
	}
}

// Register adds a new running process to the registry.
func (r *ProcessRegistry) Register(pid int, command, logPath string) *TrackedProcess {
	r.mu.Lock()
	defer r.mu.Unlock()

	proc := &TrackedProcess{
		PID:       pid,
		Command:   command,
		StartTime: time.Now().UTC(),
		LogPath:   logPath,
		Status:    "running",
		ExitCode:  0,
	}
	r.processes[pid] = proc
	return proc
}

// MarkExited updates the status and exit code of a completed process.
func (r *ProcessRegistry) MarkExited(pid int, exitCode int) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if proc, exists := r.processes[pid]; exists {
		proc.Status = "exited"
		proc.ExitCode = exitCode
	}
}

// Get returns the process with the given PID if present.
func (r *ProcessRegistry) Get(pid int) (*TrackedProcess, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	proc, exists := r.processes[pid]
	if !exists {
		return nil, false
	}
	copy := *proc
	return &copy, true
}

// List returns a snapshot of all tracked processes.
func (r *ProcessRegistry) List() []*TrackedProcess {
	r.mu.RLock()
	defer r.mu.RUnlock()

	snapshot := make([]*TrackedProcess, 0, len(r.processes))
	for _, proc := range r.processes {
		copy := *proc
		snapshot = append(snapshot, &copy)
	}
	return snapshot
}

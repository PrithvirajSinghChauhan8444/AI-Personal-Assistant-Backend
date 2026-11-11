package orchestrator

import (
	"errors"
	"sync"

	"assistant/src/orchestrator/planner"
	"assistant/src/orchestrator/safety"
	"assistant/src/orchestrator/session"
)

var (
	// ErrNilStore indicates the orchestrator was provided a nil session.Store.
	ErrNilStore = errors.New("session store cannot be nil")
	// ErrPendingApprovalNotFound is returned when no in-flight turn is awaiting the provided request ID.
	ErrPendingApprovalNotFound = errors.New("no pending approval found for request id")
)

// Orchestrator is an alias for Host to maintain seamless compatibility.
type Orchestrator = Host

// Config holds configuration parameters for initializing the Layer 2 Host and Controller.
type Config struct {
	Store          session.Store
	Gatekeeper     *safety.Gatekeeper
	Manager        *planner.ManagerAgent
	PromptFilePath string
	Executor       TurnExecutor
	ArtifactsDir   string
}

// New creates and wires the Host (Part 1) with the Controller (Part 2).
func New(cfg Config) (*Host, error) {
	if cfg.Store == nil {
		return nil, ErrNilStore
	}

	spill := NewArtifactSpillover(cfg.ArtifactsDir, DefaultSpilloverThresholdBytes)

	// Part 2: Real Orchestrator Controller (LLM, DAG, Safety, Workers)
	ctrl := NewController(ControllerConfig{
		Manager:        cfg.Manager,
		Gatekeeper:     cfg.Gatekeeper,
		Executor:       cfg.Executor,
		Spillover:      spill,
		PromptFilePath: cfg.PromptFilePath,
	})

	// Part 1: Host (SQLite Session Store, Message History, Checkpoints)
	host, err := NewHost(HostConfig{
		Store:      cfg.Store,
		Controller: ctrl,
	})
	if err != nil {
		return nil, err
	}

	return host, nil
}

// stringAccumulator is a thread-safe string buffer.
type stringAccumulator struct {
	mu  sync.Mutex
	buf []byte
}

func (sb *stringAccumulator) WriteString(s string) {
	sb.mu.Lock()
	defer sb.mu.Unlock()
	sb.buf = append(sb.buf, s...)
}

func (sb *stringAccumulator) String() string {
	sb.mu.Lock()
	defer sb.mu.Unlock()
	return string(sb.buf)
}

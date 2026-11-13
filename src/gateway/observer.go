package gateway

import (
	"context"
	"errors"
	"sync"
	"time"
)

var (
	// ErrSnapshotNotFound is returned when no active snapshot exists for a requested session.
	ErrSnapshotNotFound = errors.New("turn snapshot not found for session")
	// ErrNilObserver is returned when attempting to register a nil ExecutionObserver.
	ErrNilObserver = errors.New("observer cannot be nil")
)

const (
	// DefaultMaxRecentLogs defines default ring buffer capacity for live logs in a snapshot.
	DefaultMaxRecentLogs = 50
	// DefaultMaxTurnLogs defines the maximum logs retained per historical turn.
	DefaultMaxTurnLogs = 500
	// DefaultMaxActiveSnapshots defines the maximum concurrent session snapshots retained in RAM.
	DefaultMaxActiveSnapshots = 200
	// DefaultMaxHistoricalTurns defines the maximum turns retained in memory before FIFO eviction.
	DefaultMaxHistoricalTurns = 100
)

// PersistentObserverStore defines database storage for completed turn snapshots and logs.
type PersistentObserverStore interface {
	SaveTurnLog(ctx context.Context, entry LogEntry) error
	GetHistoricalTurnLogs(ctx context.Context, turnID string) ([]LogEntry, error)
}

// ExecutionObserver defines the unified contract for adapters and telemetry listeners.
type ExecutionObserver interface {
	OnEvent(ctx context.Context, ev OutboundEvent)
}

// ObserverFunc adapts a function to satisfy the ExecutionObserver interface.
type ObserverFunc func(ctx context.Context, ev OutboundEvent)

// OnEvent invokes the underlying observer function.
func (f ObserverFunc) OnEvent(ctx context.Context, ev OutboundEvent) {
	f(ctx, ev)
}

// ObserverHub coordinates observer subscription, real-time snapshot tracking, and log indexing.
type ObserverHub struct {
	mu                 sync.RWMutex
	observers          map[string]ExecutionObserver
	snapshots          map[string]*TurnSnapshot // Keyed by session_id
	turnLogs           map[string][]LogEntry    // Keyed by turn_id
	sessionOrder       []string                 // FIFO tracking for snapshot eviction
	turnOrder          []string                 // FIFO tracking for log eviction
	maxRecentLogs      int
	maxTurnLogs        int
	maxActiveSnapshots int
	maxHistoricalTurns int
	persistentStore    PersistentObserverStore
}

// NewObserverHub creates an initialized ObserverHub.
func NewObserverHub() *ObserverHub {
	return &ObserverHub{
		observers:          make(map[string]ExecutionObserver),
		snapshots:          make(map[string]*TurnSnapshot),
		turnLogs:           make(map[string][]LogEntry),
		sessionOrder:       make([]string, 0),
		turnOrder:          make([]string, 0),
		maxRecentLogs:      DefaultMaxRecentLogs,
		maxTurnLogs:        DefaultMaxTurnLogs,
		maxActiveSnapshots: DefaultMaxActiveSnapshots,
		maxHistoricalTurns: DefaultMaxHistoricalTurns,
	}
}

// SetPersistentStore attaches a database store for historical logs and diagnostics.
func (h *ObserverHub) SetPersistentStore(store PersistentObserverStore) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.persistentStore = store
}

// RegisterObserver registers an observer with a unique identifier.
func (h *ObserverHub) RegisterObserver(id string, obs ExecutionObserver) error {
	if obs == nil {
		return ErrNilObserver
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	h.observers[id] = obs
	return nil
}

// UnregisterObserver removes a registered observer by identifier.
func (h *ObserverHub) UnregisterObserver(id string) {
	h.mu.Lock()
	defer h.mu.Unlock()
	delete(h.observers, id)
}

// ObserverCount returns the number of active registered observers.
func (h *ObserverHub) ObserverCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.observers)
}

// GetSnapshot retrieves the current point-in-time snapshot for a session.
func (h *ObserverHub) GetSnapshot(sessionID string) (*TurnSnapshot, error) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	snap, exists := h.snapshots[sessionID]
	if !exists {
		return nil, ErrSnapshotNotFound
	}

	return h.cloneSnapshot(snap), nil
}

// GetActiveSnapshots returns clones of all currently in-flight turns (PLANNING, EXECUTING, WAITING_APPROVAL).
func (h *ObserverHub) GetActiveSnapshots() []*TurnSnapshot {
	h.mu.RLock()
	defer h.mu.RUnlock()

	list := make([]*TurnSnapshot, 0)
	for _, s := range h.snapshots {
		if s.Phase == PhasePlanning || s.Phase == PhaseExecuting || s.Phase == PhaseWaitingApproval {
			list = append(list, h.cloneSnapshot(s))
		}
	}
	return list
}

// GetAllSnapshots returns clones of all tracked session snapshots, including completed and failed turns.
func (h *ObserverHub) GetAllSnapshots() []*TurnSnapshot {
	h.mu.RLock()
	defer h.mu.RUnlock()

	list := make([]*TurnSnapshot, 0, len(h.snapshots))
	for _, s := range h.snapshots {
		list = append(list, h.cloneSnapshot(s))
	}
	return list
}

// GetTurnLogs retrieves the collected operational logs and diagnostic trace for a specific turn.
func (h *ObserverHub) GetTurnLogs(turnID string) ([]LogEntry, error) {
	h.mu.RLock()
	logs, exists := h.turnLogs[turnID]
	store := h.persistentStore
	h.mu.RUnlock()

	if exists && len(logs) > 0 {
		copied := make([]LogEntry, len(logs))
		copy(copied, logs)
		return copied, nil
	}

	if store != nil {
		return store.GetHistoricalTurnLogs(context.Background(), turnID)
	}

	return []LogEntry{}, nil
}

// ProcessEvent updates internal snapshot state, records telemetry, and notifies all observers.
func (h *ObserverHub) ProcessEvent(ctx context.Context, ev OutboundEvent) {
	if ev.Timestamp.IsZero() {
		ev.Timestamp = time.Now().UTC()
	}

	h.updateSnapshotAndLogs(ev)
	h.broadcastToObservers(ctx, ev)
}

func (h *ObserverHub) updateSnapshotAndLogs(ev OutboundEvent) {
	h.mu.Lock()
	defer h.mu.Unlock()

	snap := h.resolveOrCreateSnapshot(ev)
	h.applyEventToSnapshot(snap, ev)
	h.recordLogEntry(snap, ev)
}

func (h *ObserverHub) resolveOrCreateSnapshot(ev OutboundEvent) *TurnSnapshot {
	snap, exists := h.snapshots[ev.SessionID]
	if !exists {
		if len(h.snapshots) >= h.maxActiveSnapshots {
			h.evictOldestSnapshot()
		}

		now := ev.Timestamp
		snap = &TurnSnapshot{
			SessionID:   ev.SessionID,
			TurnID:      ev.TurnID,
			TraceID:     ev.TraceID,
			Phase:       PhaseIdle,
			ActiveAgent: ev.AgentName,
			StartedAt:   now,
			UpdatedAt:   now,
			RecentLogs:  make([]LogEntry, 0, h.maxRecentLogs),
		}
		h.snapshots[ev.SessionID] = snap
		h.sessionOrder = append(h.sessionOrder, ev.SessionID)
	}
	snap.UpdatedAt = ev.Timestamp
	if ev.TurnID != "" {
		snap.TurnID = ev.TurnID
	}
	if ev.TraceID != "" {
		snap.TraceID = ev.TraceID
	}
	if ev.AgentName != "" {
		snap.ActiveAgent = ev.AgentName
	}
	return snap
}

func (h *ObserverHub) evictOldestSnapshot() {
	for i, sessID := range h.sessionOrder {
		if s, ok := h.snapshots[sessID]; ok && (s.Phase == PhaseCompleted || s.Phase == PhaseFailed) {
			delete(h.snapshots, sessID)
			h.sessionOrder = append(h.sessionOrder[:i], h.sessionOrder[i+1:]...)
			return
		}
	}
	if len(h.sessionOrder) > 0 {
		oldest := h.sessionOrder[0]
		delete(h.snapshots, oldest)
		h.sessionOrder = h.sessionOrder[1:]
	}
}

func (h *ObserverHub) evictOldestTurnLog() {
	if len(h.turnOrder) > 0 {
		oldest := h.turnOrder[0]
		delete(h.turnLogs, oldest)
		h.turnOrder = h.turnOrder[1:]
	}
}

func (h *ObserverHub) applyEventToSnapshot(snap *TurnSnapshot, ev OutboundEvent) {
	switch ev.Type {
	case EventPhaseChange:
		if ev.Phase != "" {
			snap.Phase = ev.Phase
		}
		if ev.Phase != PhaseWaitingApproval {
			snap.PendingHITL = nil
		}

	case EventPlanCreated:
		if ev.Plan != nil {
			snap.Plan = ev.Plan
			snap.Subtasks = ev.Plan.SubTasks
		}

	case EventSubtaskStart:
		if ev.Subtask != nil {
			h.updateSubtaskInSnapshot(snap, ev.Subtask.SubtaskID, func(item *SubtaskItemInfo) {
				item.Status = "IN_PROGRESS"
				if ev.Subtask.Worker != "" {
					item.AssignedWorker = ev.Subtask.Worker
				}
			})
			snap.ActiveAction = &ActiveActionInfo{
				Type:      "SUBTASK",
				Name:      ev.Subtask.Worker,
				SubtaskID: ev.Subtask.SubtaskID,
				StartedAt: ev.Timestamp,
			}
		}

	case EventSubtaskProgress:
		if ev.Subtask != nil {
			h.updateSubtaskInSnapshot(snap, ev.Subtask.SubtaskID, func(item *SubtaskItemInfo) {
				if ev.Subtask.Status != "" {
					item.Status = ev.Subtask.Status
				}
			})
		}

	case EventSubtaskComplete:
		if ev.Subtask != nil {
			h.updateSubtaskInSnapshot(snap, ev.Subtask.SubtaskID, func(item *SubtaskItemInfo) {
				item.Status = "COMPLETED"
				item.Output = ev.Subtask.Output
				item.ArtifactPath = ev.Subtask.ArtifactPath
				item.DurationMs = ev.Subtask.DurationMs
			})
			if snap.ActiveAction != nil && snap.ActiveAction.SubtaskID == ev.Subtask.SubtaskID {
				snap.ActiveAction = nil
			}
		}

	case EventSubtaskFailed:
		if ev.Subtask != nil {
			h.updateSubtaskInSnapshot(snap, ev.Subtask.SubtaskID, func(item *SubtaskItemInfo) {
				item.Status = "FAILED"
				item.Error = ev.Subtask.Error
			})
			if snap.ActiveAction != nil && snap.ActiveAction.SubtaskID == ev.Subtask.SubtaskID {
				snap.ActiveAction = nil
			}
		}

	case EventToolCall:
		if ev.ToolCall != nil {
			snap.ActiveAction = &ActiveActionInfo{
				Type:      "TOOL",
				Name:      ev.ToolCall.ToolName,
				CallID:    ev.ToolCall.CallID,
				Arguments: ev.ToolCall.Arguments,
				StartedAt: ev.Timestamp,
			}
		}

	case EventToolResult:
		if snap.ActiveAction != nil && snap.ActiveAction.Type == "TOOL" {
			snap.ActiveAction.ElapsedMs = ev.Timestamp.Sub(snap.ActiveAction.StartedAt).Milliseconds()
			snap.ActiveAction = nil
		}

	case EventThoughtChunk:
		snap.ThoughtsBuffer += ev.TextDelta

	case EventTokenChunk:
		snap.AnswerBuffer += ev.TextDelta

	case EventHITLRequest:
		snap.Phase = PhaseWaitingApproval
		snap.PendingHITL = ev.HITL

	case EventTurnComplete:
		snap.Phase = PhaseCompleted
		snap.ActiveAction = nil
		snap.PendingHITL = nil

	case EventTurnError:
		snap.Phase = PhaseFailed
		snap.ActiveAction = nil
		snap.PendingHITL = nil
	}
}

func (h *ObserverHub) updateSubtaskInSnapshot(snap *TurnSnapshot, subtaskID string, updateFn func(*SubtaskItemInfo)) {
	for i := range snap.Subtasks {
		if snap.Subtasks[i].ID == subtaskID {
			updateFn(&snap.Subtasks[i])
			break
		}
	}
	if snap.Plan != nil {
		for i := range snap.Plan.SubTasks {
			if snap.Plan.SubTasks[i].ID == subtaskID {
				updateFn(&snap.Plan.SubTasks[i])
				break
			}
		}
	}
}

func (h *ObserverHub) recordLogEntry(snap *TurnSnapshot, ev OutboundEvent) {
	var entry LogEntry

	switch ev.Type {
	case EventSystemLog:
		if ev.Log != nil {
			entry = *ev.Log
		} else {
			entry = LogEntry{
				Timestamp: ev.Timestamp,
				Severity:  LogSeverityInfo,
				Component: ev.AgentName,
				Message:   ev.StatusMsg,
				TurnID:    snap.TurnID,
			}
		}

	case EventStatusUpdate:
		entry = LogEntry{
			Timestamp: ev.Timestamp,
			Severity:  LogSeverityInfo,
			Component: ev.AgentName,
			Message:   ev.StatusMsg,
			TurnID:    snap.TurnID,
		}

	case EventTurnError:
		entry = LogEntry{
			Timestamp: ev.Timestamp,
			Severity:  LogSeverityError,
			Component: ev.AgentName,
			Message:   ev.Error,
			TurnID:    snap.TurnID,
		}

	case EventPlanDiagnostic:
		msg := ev.StatusMsg
		if ev.Diagnostic != nil {
			msg = ev.Diagnostic.Reason
		}
		entry = LogEntry{
			Timestamp: ev.Timestamp,
			Severity:  LogSeverityWarn,
			Component: "Planner",
			Message:   msg,
			TurnID:    snap.TurnID,
		}

	default:
		return
	}

	if entry.TurnID == "" {
		entry.TurnID = snap.TurnID
	}

	// Append to snapshot recent logs ring buffer
	if len(snap.RecentLogs) >= h.maxRecentLogs {
		snap.RecentLogs = snap.RecentLogs[1:]
	}
	snap.RecentLogs = append(snap.RecentLogs, entry)

	// Append to historical turn logs index
	if snap.TurnID != "" {
		turnList, exists := h.turnLogs[snap.TurnID]
		if !exists {
			if len(h.turnLogs) >= h.maxHistoricalTurns {
				h.evictOldestTurnLog()
			}
			h.turnOrder = append(h.turnOrder, snap.TurnID)
		}
		if len(turnList) < h.maxTurnLogs {
			h.turnLogs[snap.TurnID] = append(turnList, entry)
		}
	}

	// Persist log if database store attached
	if h.persistentStore != nil {
		go func(e LogEntry) {
			_ = h.persistentStore.SaveTurnLog(context.Background(), e)
		}(entry)
	}
}

func (h *ObserverHub) broadcastToObservers(ctx context.Context, ev OutboundEvent) {
	h.mu.RLock()
	observers := make([]ExecutionObserver, 0, len(h.observers))
	for _, obs := range h.observers {
		observers = append(observers, obs)
	}
	h.mu.RUnlock()

	for _, obs := range observers {
		func(o ExecutionObserver) {
			defer func() {
				_ = recover() // Isolate hub from panics in custom observers
			}()
			o.OnEvent(ctx, ev)
		}(obs)
	}
}

func (h *ObserverHub) cloneSnapshot(src *TurnSnapshot) *TurnSnapshot {
	if src == nil {
		return nil
	}
	clone := *src

	if src.ActiveAction != nil {
		aa := *src.ActiveAction
		clone.ActiveAction = &aa
	}
	if src.Plan != nil {
		p := *src.Plan
		p.SubTasks = make([]SubtaskItemInfo, len(src.Plan.SubTasks))
		copy(p.SubTasks, src.Plan.SubTasks)
		clone.Plan = &p
	}
	if src.Subtasks != nil {
		clone.Subtasks = make([]SubtaskItemInfo, len(src.Subtasks))
		copy(clone.Subtasks, src.Subtasks)
	}
	if src.PendingHITL != nil {
		hitl := *src.PendingHITL
		clone.PendingHITL = &hitl
	}
	if src.RecentLogs != nil {
		clone.RecentLogs = make([]LogEntry, len(src.RecentLogs))
		copy(clone.RecentLogs, src.RecentLogs)
	}

	return &clone
}

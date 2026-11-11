package engine

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"runtime/debug"
	"sync"
	"time"

	"assistant/src/gateway"

	"github.com/google/uuid"
)

var (
	ErrModuleNotFound = errors.New("module not found")
	ErrExecutionAborted = errors.New("execution aborted by user")
)

// Supervisor oversees module execution, runtime process control, and live streaming.
type Supervisor struct {
	registry    *Registry
	recorder    *Recorder
	activeExecs sync.Map // map[string]context.CancelFunc
	pendingHITL sync.Map // map[string]chan gateway.HITLResponse
}

// NewSupervisor constructs an execution supervisor.
func NewSupervisor(registry *Registry, recorder *Recorder) *Supervisor {
	return &Supervisor{
		registry: registry,
		recorder: recorder,
	}
}

// Execute runs a module with full runtime telemetry, stream capture, panic recovery, and abort tracking.
func (s *Supervisor) Execute(
	parentCtx context.Context,
	moduleID string,
	inputRaw json.RawMessage,
	streamOut chan<- StreamEvent,
) (*ExecutionRecord, error) {
	mod, exists := s.registry.Get(moduleID)
	if !exists {
		return nil, fmt.Errorf("%w: %s", ErrModuleNotFound, moduleID)
	}

	execID := uuid.New().String()
	traceID, spanID := TraceFromContext(parentCtx)
	if traceID == "" {
		traceID = uuid.New().String()
	}
	if spanID == "" {
		spanID = uuid.New().String()[:16]
	}

	// Capture initial runtime metrics (allocs, goroutines)
	_, finishTelemetry := SnapshotRuntimeTelemetry(traceID, spanID)

	execCtx, cancel := context.WithCancel(parentCtx)
	s.activeExecs.Store(execID, cancel)
	defer s.activeExecs.Delete(execID)

	rec := &ExecutionRecord{
		ID:         execID,
		ModuleID:   mod.ID,
		ModuleName: mod.Name,
		Category:   mod.Category,
		StartedAt:  time.Now().UTC(),
		Input:      inputRaw,
		Events:     make([]StreamEvent, 0),
		Logs:       make([]GoLogEntry, 0),
		Status:     "RUNNING",
	}

	recordLog := func(level, source, msg string, fields map[string]any) {
		logEntry := GoLogEntry{
			Timestamp:   time.Now().UTC(),
			Level:       level,
			Source:      source,
			ExecutionID: execID,
			TraceID:     traceID,
			Message:     msg,
			Fields:      fields,
		}
		rec.Logs = append(rec.Logs, logEntry)
		GlobalTelemetry.RecordGoLog(logEntry)

		// Also stream log to UI
		if streamOut != nil {
			select {
			case streamOut <- StreamEvent{
				Timestamp: logEntry.Timestamp,
				Type:      "GO_LOG",
				AgentName: source,
				Payload:   logEntry,
			}:
			case <-execCtx.Done():
			}
		}
	}

	recordLog("INFO", "supervisor", fmt.Sprintf("Initiating execution for module %q (id: %s)", mod.Name, mod.ID), map[string]any{
		"trace_id": traceID,
		"span_id":  spanID,
	})

	// Internal channel to intercept and record all streamed events
	internalStream := make(chan StreamEvent, 128)
	var eventWg sync.WaitGroup
	eventWg.Add(1)

	var eventsMu sync.Mutex
	eventIndex := 0

	go func() {
		defer eventWg.Done()
		for ev := range internalStream {
			eventsMu.Lock()
			eventIndex++
			ev.Index = eventIndex
			if ev.Timestamp.IsZero() {
				ev.Timestamp = time.Now().UTC()
			}
			rec.Events = append(rec.Events, ev)
			eventsMu.Unlock()

			// Forward to caller (e.g. SSE response writer)
			if streamOut != nil {
				select {
				case streamOut <- ev:
				case <-execCtx.Done():
				}
			}
		}
	}()

	start := time.Now()

	// Safe runner with panic recovery
	runErr := func() (err error) {
		defer func() {
			if r := recover(); r != nil {
				stack := string(debug.Stack())
				panicStr := fmt.Sprintf("RECOVERED PANIC: %v\n\nFull Stack Trace:\n%s", r, stack)
				rec.Panic = &panicStr
				rec.Status = "PANIC"
				err = fmt.Errorf("module panicked: %v", r)

				recordLog("ERROR", "supervisor", fmt.Sprintf("Recovered panic during execution: %v", r), map[string]any{
					"panic": r,
					"stack": stack,
				})

				// Emit panic event into the live stream
				internalStream <- StreamEvent{
					Type:      "PANIC_STACK",
					AgentName: "WorkbenchSupervisor",
					Payload:   panicStr,
				}
			}
		}()

		recordLog("DEBUG", "supervisor", "Invoking module execution function", nil)
		out, executeErr := mod.Execute(execCtx, inputRaw, internalStream)
		rec.Output = out
		return executeErr
	}()

	// Close internal stream and wait for recording goroutine to finish
	close(internalStream)
	eventWg.Wait()

	duration := time.Since(start)
	rec.CompletedAt = time.Now().UTC()
	rec.DurationUs = duration.Microseconds()
	rec.DurationFormatted = formatDuration(duration)
	rec.Telemetry = finishTelemetry()

	if execCtx.Err() == context.Canceled {
		rec.Aborted = true
		rec.Status = "ABORTED"
		errMsg := "Execution aborted by user"
		rec.Error = &errMsg
		recordLog("WARN", "supervisor", "Module execution aborted by user context cancellation", nil)
	} else if rec.Status != "PANIC" {
		if runErr != nil {
			rec.Status = "ERROR"
			errMsg := runErr.Error()
			rec.Error = &errMsg
			recordLog("ERROR", "supervisor", fmt.Sprintf("Module execution returned error: %v", runErr), nil)
		} else {
			rec.Status = "SUCCESS"
			recordLog("INFO", "supervisor", fmt.Sprintf("Module execution finished successfully in %s", rec.DurationFormatted), map[string]any{
				"duration_us": rec.DurationUs,
				"mem_delta":   rec.Telemetry.MemDeltaBytes,
				"goroutines":  rec.Telemetry.GoroutinesEnd,
			})
		}
	}

	// Persist to disk flight recorder
	if s.recorder != nil {
		_ = s.recorder.Save(rec)
	}

	return rec, runErr
}

// Abort triggers cancellation of an in-flight execution context.
func (s *Supervisor) Abort(executionID string) bool {
	val, ok := s.activeExecs.Load(executionID)
	if !ok {
		return false
	}
	cancel, isCancel := val.(context.CancelFunc)
	if isCancel {
		cancel()
		return true
	}
	return false
}

// RegisterHITL registers a waiting channel for a Human-In-The-Loop approval request.
func (s *Supervisor) RegisterHITL(requestID string, ch chan gateway.HITLResponse) {
	s.pendingHITL.Store(requestID, ch)
}

// SubmitHITL delivers the human decision back to the waiting module.
func (s *Supervisor) SubmitHITL(resp gateway.HITLResponse) bool {
	val, ok := s.pendingHITL.Load(resp.RequestID)
	if !ok {
		return false
	}
	ch, isChan := val.(chan gateway.HITLResponse)
	if isChan {
		select {
		case ch <- resp:
			s.pendingHITL.Delete(resp.RequestID)
			return true
		default:
			return false
		}
	}
	return false
}

// FormatDuration formats a time.Duration cleanly for developer telemetry.
func FormatDuration(d time.Duration) string {
	if d < time.Millisecond {
		return fmt.Sprintf("%dµs", d.Microseconds())
	}
	if d < time.Second {
		return fmt.Sprintf("%.2fms", float64(d.Microseconds())/1000.0)
	}
	return fmt.Sprintf("%.2fs", d.Seconds())
}

func formatDuration(d time.Duration) string {
	return FormatDuration(d)
}

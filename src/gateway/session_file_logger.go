package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"
)

var safeSessionIDRegex = regexp.MustCompile(`[^a-zA-Z0-9_\-]`)

// SessionFileLogger automatically appends formatted chronological operational logs
// for every active session into dedicated files on disk (e.g., workspace/logs/sessions/<session_id>.log).
type SessionFileLogger struct {
	mu           sync.Mutex
	baseDir      string
	files        map[string]*os.File
	tokenBuffers map[string]*strings.Builder
}

// NewSessionFileLogger initializes a file session logger rooted in baseDir.
func NewSessionFileLogger(baseDir string) (*SessionFileLogger, error) {
	if strings.TrimSpace(baseDir) == "" {
		baseDir = filepath.Join("workspace", "logs", "sessions")
	}

	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create session logs directory %q: %w", baseDir, err)
	}

	return &SessionFileLogger{
		baseDir:      baseDir,
		files:        make(map[string]*os.File),
		tokenBuffers: make(map[string]*strings.Builder),
	}, nil
}

// OnEvent formats and appends execution events to the respective session's log file.
func (l *SessionFileLogger) OnEvent(ctx context.Context, ev OutboundEvent) {
	select {
	case <-ctx.Done():
		return
	default:
	}

	sessionID := sanitizeSessionID(ev.SessionID)
	ts := ev.Timestamp
	if ts.IsZero() {
		ts = time.Now().UTC()
	}
	isoTime := ts.Format(time.RFC3339Nano)

	l.mu.Lock()
	defer l.mu.Unlock()

	// Handle token accumulation
	if ev.Type == EventTokenChunk {
		buf, exists := l.tokenBuffers[sessionID]
		if !exists {
			buf = &strings.Builder{}
			l.tokenBuffers[sessionID] = buf
		}
		if strings.EqualFold(ev.AgentName, "summarizer") && buf.Len() > 0 && !strings.Contains(buf.String(), "[Summarizer Output]") {
			buf.Reset()
			buf.WriteString("[Summarizer Output]\n")
		}
		buf.WriteString(ev.TextDelta)
		return
	}

	f, err := l.getOrCreateFileLocked(sessionID)
	if err != nil {
		return
	}

	switch ev.Type {
	case EventPhaseChange:
		fmt.Fprintf(f, "[%s] [PHASE_CHANGE] Phase: %s | Status: %s\n", isoTime, ev.Phase, ev.StatusMsg)

	case EventPlanCreated:
		if ev.Plan != nil {
			fmt.Fprintf(f, "[%s] [PLAN_CREATED] Goal: %s | Subtasks: %d\n", isoTime, ev.Plan.PrimaryGoal, len(ev.Plan.SubTasks))
			for _, st := range ev.Plan.SubTasks {
				fmt.Fprintf(f, "[%s] [PLAN_TASK] Subtask %s [@%s] (DependsOn: %v): %s\n", isoTime, st.ID, st.AssignedWorker, st.DependsOn, st.Description)
			}
		}

	case EventPlanDiagnostic:
		if ev.Diagnostic != nil {
			fmt.Fprintf(f, "[%s] [PLAN_DIAGNOSTIC] Goal: %s | Reason: %s | Error: %s\n", isoTime, ev.Diagnostic.Goal, ev.Diagnostic.Reason, ev.Diagnostic.Error)
		}

	case EventSubtaskStart:
		if ev.Subtask != nil {
			fmt.Fprintf(f, "[%s] [SUBTASK_START] Subtask: %s | Worker: %s | Desc: %s\n", isoTime, ev.Subtask.SubtaskID, ev.Subtask.Worker, ev.Subtask.Description)
		}

	case EventSubtaskComplete:
		if ev.Subtask != nil {
			fmt.Fprintf(f, "[%s] [SUBTASK_COMPLETE] Subtask: %s | Worker: %s | Duration: %dms | Artifact: %s\n", isoTime, ev.Subtask.SubtaskID, ev.Subtask.Worker, ev.Subtask.DurationMs, ev.Subtask.ArtifactPath)
		}

	case EventSubtaskFailed:
		if ev.Subtask != nil {
			fmt.Fprintf(f, "[%s] [SUBTASK_FAILED] Subtask: %s | Worker: %s | Error: %s\n", isoTime, ev.Subtask.SubtaskID, ev.Subtask.Worker, ev.Subtask.Error)
		}

	case EventThoughtChunk:
		if strings.TrimSpace(ev.TextDelta) != "" {
			fmt.Fprintf(f, "[%s] [THOUGHT] Agent: %s | Content: %s\n", isoTime, ev.AgentName, strings.TrimSpace(ev.TextDelta))
		}

	case EventToolCall:
		if ev.ToolCall != nil {
			args := ev.ToolCall.ArgsJSON
			if args == "" && ev.ToolCall.Arguments != nil {
				b, _ := json.Marshal(ev.ToolCall.Arguments)
				args = string(b)
			}
			fmt.Fprintf(f, "[%s] [TOOL_CALL] Agent: %s | Tool: %s | CallID: %s | Args: %s\n", isoTime, ev.AgentName, ev.ToolCall.ToolName, ev.ToolCall.CallID, args)
		}

	case EventToolResult:
		if ev.ToolResult != nil {
			fmt.Fprintf(f, "[%s] [TOOL_RESULT] Agent: %s | ToolResult CallID: %s\n", isoTime, ev.AgentName, ev.ToolResult.CallID)
		}

	case EventHITLRequest:
		if ev.HITL != nil {
			fmt.Fprintf(f, "[%s] [HITL_REQUEST] RequestID: %s | Tool: %s | Reason: %s\n", isoTime, ev.HITL.RequestID, ev.HITL.ToolName, ev.HITL.Reason)
		}

	case EventTurnComplete:
		metricsStr := "none"
		if ev.Metrics != nil {
			metricsStr = fmt.Sprintf("duration=%dms, in_tokens=%d, out_tokens=%d", ev.Metrics.TotalDurationMs, ev.Metrics.PromptTokens, ev.Metrics.CompletionTokens)
		}
		fmt.Fprintf(f, "[%s] [TURN_COMPLETE] TurnID: %s | Metrics: %s\n", isoTime, ev.TurnID, metricsStr)

		// Flush accumulated final answer if present
		if buf, exists := l.tokenBuffers[sessionID]; exists && buf.Len() > 0 {
			answer := strings.TrimSpace(buf.String())
			fmt.Fprintf(f, "[%s] [FINAL_RESPONSE]\n%s\n---\n", isoTime, answer)
			buf.Reset()
		}

	case EventTurnError:
		fmt.Fprintf(f, "[%s] [TURN_ERROR] TurnID: %s | Error: %s\n", isoTime, ev.TurnID, ev.Error)
	}

	_ = f.Sync()
}

// Close flushes and closes all underlying open session log files.
func (l *SessionFileLogger) Close() error {
	l.mu.Lock()
	defer l.mu.Unlock()

	var firstErr error
	for id, f := range l.files {
		if err := f.Close(); err != nil && firstErr == nil {
			firstErr = err
		}
		delete(l.files, id)
	}
	return firstErr
}

func (l *SessionFileLogger) getOrCreateFileLocked(sessionID string) (*os.File, error) {
	if f, exists := l.files[sessionID]; exists {
		return f, nil
	}

	filePath := filepath.Join(l.baseDir, sessionID+".log")
	f, err := os.OpenFile(filePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return nil, err
	}

	l.files[sessionID] = f
	return f, nil
}

func sanitizeSessionID(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "default"
	}
	cleaned := safeSessionIDRegex.ReplaceAllString(raw, "_")
	if len(cleaned) > 128 {
		cleaned = cleaned[:128]
	}
	return cleaned
}


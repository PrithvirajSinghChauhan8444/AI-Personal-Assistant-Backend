package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"sync"
	"time"
)

// TerminalLogger renders live execution events directly to a terminal writer.
type TerminalLogger struct {
	mu     sync.Mutex
	writer io.Writer
}

// NewTerminalLogger constructs a live streaming logger attached to the given writer.
func NewTerminalLogger(w io.Writer) *TerminalLogger {
	if w == nil {
		w = os.Stdout
	}
	return &TerminalLogger{
		writer: w,
	}
}

// OnEvent processes and formats execution events for terminal display.
func (l *TerminalLogger) OnEvent(ctx context.Context, ev OutboundEvent) {
	select {
	case <-ctx.Done():
		return
	default:
	}

	ts := ev.Timestamp
	if ts.IsZero() {
		ts = time.Now()
	}
	timeStr := ts.Format("15:04:05.000")
	sessID := shortSessionID(ev.SessionID)

	l.mu.Lock()
	defer l.mu.Unlock()

	switch ev.Type {
	case EventPhaseChange:
		fmt.Fprintf(l.writer, "[%s] [%s] 🔄 PHASE: %s — %s\n", timeStr, sessID, ev.Phase, ev.StatusMsg)

	case EventPlanCreated:
		if ev.Plan != nil {
			fmt.Fprintf(l.writer, "[%s] [%s] 📋 PLAN: %s (%d subtasks planned)\n", timeStr, sessID, ev.Plan.PrimaryGoal, len(ev.Plan.SubTasks))
			for _, st := range ev.Plan.SubTasks {
				fmt.Fprintf(l.writer, "  ├─ Subtask %s [@%s]: %s\n", st.ID, st.AssignedWorker, st.Description)
			}
		}

	case EventSubtaskStart:
		if ev.Subtask != nil {
			fmt.Fprintf(l.writer, "[%s] [%s] ⚙️  SUBTASK START: %s [@%s] %s\n", timeStr, sessID, ev.Subtask.SubtaskID, ev.Subtask.Worker, ev.Subtask.Description)
		}

	case EventSubtaskComplete:
		if ev.Subtask != nil {
			fmt.Fprintf(l.writer, "[%s] [%s] ✅ SUBTASK COMPLETE: %s (%dms)\n", timeStr, sessID, ev.Subtask.SubtaskID, ev.Subtask.DurationMs)
		}

	case EventSubtaskFailed:
		if ev.Subtask != nil {
			fmt.Fprintf(l.writer, "[%s] [%s] ❌ SUBTASK FAILED: %s: %s\n", timeStr, sessID, ev.Subtask.SubtaskID, ev.Subtask.Error)
		}

	case EventThoughtChunk:
		if strings.TrimSpace(ev.TextDelta) != "" {
			fmt.Fprintf(l.writer, "[%s] [%s] 💭 [@%s]: %s\n", timeStr, sessID, ev.AgentName, strings.TrimSpace(ev.TextDelta))
		}

	case EventToolCall:
		if ev.ToolCall != nil {
			args := ev.ToolCall.ArgsJSON
			if args == "" && ev.ToolCall.Arguments != nil {
				b, _ := json.Marshal(ev.ToolCall.Arguments)
				args = string(b)
			}
			if len(args) > 120 {
				args = args[:117] + "..."
			}
			fmt.Fprintf(l.writer, "[%s] [%s] 🛠️  TOOL CALL: [@%s] %s(%s)\n", timeStr, sessID, ev.AgentName, ev.ToolCall.ToolName, args)
		}

	case EventToolResult:
		if ev.ToolResult != nil {
			fmt.Fprintf(l.writer, "[%s] [%s] 🔧 TOOL RESULT: [@%s] call_id=%s\n", timeStr, sessID, ev.AgentName, ev.ToolResult.CallID)
		}

	case EventHITLRequest:
		if ev.HITL != nil {
			fmt.Fprintf(l.writer, "[%s] [%s] ✋ HITL REQUIRED: %s (%s)\n", timeStr, sessID, ev.HITL.ToolName, ev.HITL.Reason)
		}

	case EventTurnComplete:
		metricsInfo := ""
		if ev.Metrics != nil {
			metricsInfo = fmt.Sprintf(" (%dms | in=%d, out=%d tokens)", ev.Metrics.TotalDurationMs, ev.Metrics.PromptTokens, ev.Metrics.CompletionTokens)
		}
		fmt.Fprintf(l.writer, "[%s] [%s] 🏁 TURN COMPLETE%s\n", timeStr, sessID, metricsInfo)

	case EventTurnError:
		fmt.Fprintf(l.writer, "[%s] [%s] ⚠️  TURN ERROR: %s\n", timeStr, sessID, ev.Error)
	}
}

func shortSessionID(s string) string {
	if len(s) > 12 {
		return s[:12]
	}
	if s == "" {
		return "system"
	}
	return s
}


package tui

import (
	"fmt"
	"strings"

	"assistant/src/gateway"
)

// EventDemuxer routes gateway events strictly separating user-facing response from telemetry.
type EventDemuxer struct {
	state *UIState
}

// NewEventDemuxer creates a demuxer bound to the UI state.
func NewEventDemuxer(state *UIState) *EventDemuxer {
	return &EventDemuxer{state: state}
}

// Process routes a single OutboundEvent to its appropriate destination pane.
func (d *EventDemuxer) Process(ev gateway.OutboundEvent) {
	d.state.mu.Lock()
	defer d.state.mu.Unlock()

	switch ev.Type {
	case gateway.EventTokenChunk:
		// User-facing text: streamed exclusively to active response
		d.state.ActiveResponse.WriteString(ev.TextDelta)
		d.state.IsGenerating = true
		d.state.ResponseScroll = 0 // Auto-scroll to follow generation

	case gateway.EventThoughtChunk:
		// Internal reasoning: routed exclusively to telemetry log drawer
		clean := strings.TrimSpace(ev.TextDelta)
		if clean != "" {
			d.state.appendLogLocked("THOUGHT", clean, false)
		}

	case gateway.EventThoughtComplete:
		d.state.appendLogLocked("THOUGHT", "Reasoning complete. Answering...", false)

	case gateway.EventToolCall:
		name := "unknown"
		args := ""
		if ev.ToolCall != nil {
			name = ev.ToolCall.ToolName
			args = ev.ToolCall.ArgsJSON
		}
		d.state.appendLogLocked("TOOL-CALL", fmt.Sprintf("%s %s", name, args), false)

	case gateway.EventToolResult:
		name := "tool"
		summary := ev.StatusMsg
		isErr := false
		if ev.ToolResult != nil {
			name = ev.ToolResult.ToolName
			if ev.ToolResult.Output != "" {
				summary = ev.ToolResult.Output
			}
			isErr = ev.ToolResult.IsError
		}
		if summary == "" {
			summary = "ok"
		}
		d.state.appendLogLocked("TOOL-OK", fmt.Sprintf("%s -> %s", name, summary), isErr)

	case gateway.EventPhaseChange:
		d.state.appendLogLocked("PHASE", string(ev.Phase), false)

	case gateway.EventPlanCreated:
		count := 0
		if ev.Plan != nil {
			count = len(ev.Plan.SubTasks)
		}
		d.state.appendLogLocked("PLAN", fmt.Sprintf("DAG plan created with %d task(s)", count), false)

	case gateway.EventPlanDiagnostic:
		d.state.appendLogLocked("PLAN-DIAG", ev.StatusMsg, true)

	case gateway.EventSubtaskStart:
		id := ""
		if ev.Subtask != nil {
			id = ev.Subtask.SubtaskID
		}
		d.state.appendLogLocked("SUBTASK", fmt.Sprintf("Start [%s]: %s", id, ev.StatusMsg), false)

	case gateway.EventSubtaskProgress:
		id := ""
		if ev.Subtask != nil {
			id = ev.Subtask.SubtaskID
		}
		d.state.appendLogLocked("PROGRESS", fmt.Sprintf("[%s] %s", id, ev.StatusMsg), false)

	case gateway.EventSubtaskComplete:
		id := ""
		if ev.Subtask != nil {
			id = ev.Subtask.SubtaskID
		}
		d.state.appendLogLocked("SUBTASK-OK", fmt.Sprintf("Finished [%s]", id), false)

	case gateway.EventSubtaskFailed:
		id := ""
		if ev.Subtask != nil {
			id = ev.Subtask.SubtaskID
		}
		d.state.appendLogLocked("SUBTASK-FAIL", fmt.Sprintf("Failed [%s]: %s", id, ev.Error), true)

	case gateway.EventStatusUpdate:
		d.state.StatusMessage = ev.StatusMsg
		d.state.appendLogLocked("STATUS", ev.StatusMsg, false)

	case gateway.EventSystemLog:
		msg := ev.StatusMsg
		if ev.Log != nil && ev.Log.Message != "" {
			msg = ev.Log.Message
		}
		d.state.appendLogLocked("SYS", msg, false)

	case gateway.EventHITLRequest:
		d.state.appendLogLocked("APPROVAL", fmt.Sprintf("Action pending user signoff: %s", ev.StatusMsg), false)

	case gateway.EventTurnComplete:
		d.state.IsGenerating = false
		d.finalizeTurn()

	case gateway.EventTurnError:
		d.state.IsGenerating = false
		d.state.ErrorMessage = ev.Error
		d.state.appendLogLocked("ERROR", ev.Error, true)
		d.finalizeTurn()
	}
}

// finalizeTurn commits the streamed response to conversation history.
func (d *EventDemuxer) finalizeTurn() {
	respText := strings.TrimSpace(d.state.ActiveResponse.String())
	if respText != "" {
		lines := strings.Split(respText, "\n")
		prefix := "Assistant: "
		for i, line := range lines {
			if i == 0 {
				d.state.ConversationLines = append(d.state.ConversationLines, prefix+line)
			} else {
				d.state.ConversationLines = append(d.state.ConversationLines, "           "+line)
			}
		}
	} else if d.state.ErrorMessage != "" {
		d.state.ConversationLines = append(d.state.ConversationLines, "Error: "+d.state.ErrorMessage)
	}
	d.state.ActiveResponse.Reset()
	d.state.ResponseScroll = 0
}

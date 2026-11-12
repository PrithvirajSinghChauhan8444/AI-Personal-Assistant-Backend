package cli

import (
	"fmt"
	"io"
	"strings"
	"sync"
	"time"

	"assistant/src/gateway"
)

// StreamRenderer coordinates real-time token streaming with structured harness logs.
// It ensures that status updates, tool invocations, and agent thoughts never corrupt
// or interleave awkwardly with live streaming token text.
type StreamRenderer struct {
	out                io.Writer
	inTokenStream      bool
	tokenEndsNewline   bool
	inThoughtStream    bool
	thoughtEndsNewline bool
	lastActivity       time.Time
	mu                 sync.Mutex
}

// NewStreamRenderer creates an initialized StreamRenderer.
func NewStreamRenderer(out io.Writer) *StreamRenderer {
	return &StreamRenderer{
		out:                out,
		tokenEndsNewline:   true,
		thoughtEndsNewline: true,
		lastActivity:       time.Now(),
	}
}

// RenderEvent dispatches and renders an OutboundEvent based on its event category.
func (r *StreamRenderer) RenderEvent(ev gateway.OutboundEvent) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.lastActivity = time.Now()

	switch ev.Type {
	case gateway.EventTokenChunk:
		r.renderTokenChunk(ev)
	case gateway.EventThoughtChunk:
		r.renderThoughtChunk(ev)
	case gateway.EventStatusUpdate:
		r.renderStatusUpdate(ev)
	case gateway.EventToolCall:
		r.renderToolCall(ev)
	case gateway.EventToolResult:
		r.renderToolResult(ev)
	case gateway.EventHITLRequest:
		r.renderHITLRequest(ev)
	case gateway.EventTurnComplete:
		r.renderTurnComplete(ev)
	case gateway.EventTurnError:
		r.renderTurnError(ev)
	default:
		r.ensureCleanLine()
		fmt.Fprintf(r.out, "[%s] %s\n", ev.Type, ev.StatusMsg)
	}
}

// RenderHeartbeat renders a progress heartbeat only if token streaming is inactive.
func (r *StreamRenderer) RenderHeartbeat(elapsed time.Duration) {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Never interrupt active token streaming or thought streaming with heartbeats
	if r.inTokenStream || r.inThoughtStream {
		return
	}

	fmt.Fprint(r.out, RenderHeartbeat(elapsed))
}

// Flush ensures any trailing line in progress is cleanly newline-terminated.
func (r *StreamRenderer) Flush() {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.inTokenStream {
		if !r.tokenEndsNewline {
			fmt.Fprintln(r.out)
			r.tokenEndsNewline = true
		}
		r.inTokenStream = false
	}

	if r.inThoughtStream {
		if !r.thoughtEndsNewline {
			fmt.Fprintln(r.out)
			r.thoughtEndsNewline = true
		}
		r.inThoughtStream = false
	}
}

func (r *StreamRenderer) ensureCleanLine() {
	if r.inTokenStream {
		if !r.tokenEndsNewline {
			fmt.Fprintln(r.out)
			r.tokenEndsNewline = true
		}
		r.inTokenStream = false
	}
	if r.inThoughtStream {
		if !r.thoughtEndsNewline {
			fmt.Fprintln(r.out)
			r.thoughtEndsNewline = true
		}
		r.inThoughtStream = false
	}
}

func (r *StreamRenderer) renderTokenChunk(ev gateway.OutboundEvent) {
	if r.inThoughtStream {
		if !r.thoughtEndsNewline {
			fmt.Fprintln(r.out)
			r.thoughtEndsNewline = true
		}
		r.inThoughtStream = false
	}

	if !r.inTokenStream {
		r.inTokenStream = true
		// Add a blank line separator if transitioning from logs to markdown tokens
		if r.tokenEndsNewline {
			fmt.Fprintln(r.out)
		}
	}

	fmt.Fprint(r.out, ev.TextDelta)
	r.tokenEndsNewline = strings.HasSuffix(ev.TextDelta, "\n")
}

func (r *StreamRenderer) renderThoughtChunk(ev gateway.OutboundEvent) {
	if ev.TextDelta == "" {
		return
	}

	r.ensureCleanLine()
	fmt.Fprint(r.out, RenderThought(ev.AgentName, ev.TextDelta))
	r.tokenEndsNewline = true
}

func (r *StreamRenderer) renderStatusUpdate(ev gateway.OutboundEvent) {
	r.ensureCleanLine()
	fmt.Fprint(r.out, RenderStatus(ev.AgentName, ev.StatusMsg))
	r.tokenEndsNewline = true
}

func (r *StreamRenderer) renderToolCall(ev gateway.OutboundEvent) {
	r.ensureCleanLine()
	argsJSON := ""
	toolName := ""
	callID := ""
	if ev.ToolCall != nil {
		argsJSON = ev.ToolCall.ArgsJSON
		toolName = ev.ToolCall.ToolName
		callID = ev.ToolCall.CallID
	}
	fmt.Fprint(r.out, RenderToolCall(ev.AgentName, toolName, argsJSON, callID))
	r.tokenEndsNewline = true
}

func (r *StreamRenderer) renderToolResult(ev gateway.OutboundEvent) {
	r.ensureCleanLine()
	if ev.ToolResult != nil {
		fmt.Fprint(r.out, RenderToolResult(
			ev.AgentName,
			ev.ToolResult.ToolName,
			ev.ToolResult.ExitCode,
			ev.ToolResult.Output,
			ev.ToolResult.ArtifactPath,
			ev.ToolResult.DurationMs,
			ev.ToolResult.IsError,
		))
	} else {
		fmt.Fprint(r.out, RenderToolResult(
			ev.AgentName,
			"",
			0,
			ev.StatusMsg,
			"",
			0,
			false,
		))
	}
	r.tokenEndsNewline = true
}

func (r *StreamRenderer) renderHITLRequest(ev gateway.OutboundEvent) {
	r.ensureCleanLine()
	fmt.Fprint(r.out, RenderHITLPrompt(ev.HITL))
	r.tokenEndsNewline = true
}

func (r *StreamRenderer) renderTurnComplete(ev gateway.OutboundEvent) {
	r.ensureCleanLine()
	fmt.Fprint(r.out, RenderTurnMetrics(ev.Metrics))
	r.tokenEndsNewline = true
}

func (r *StreamRenderer) renderTurnError(ev gateway.OutboundEvent) {
	r.ensureCleanLine()
	fmt.Fprint(r.out, RenderError(ev.Error))
	r.tokenEndsNewline = true
}

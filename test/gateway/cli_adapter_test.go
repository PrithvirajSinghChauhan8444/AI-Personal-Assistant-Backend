package gateway_test

import (
	"bytes"
	"strings"
	"testing"
	"time"

	"assistant/src/bridge/protocol"
	"assistant/src/bridge/supervisor"
	"assistant/src/gateway"
	"assistant/src/gateway/adapters/cli"
)

func TestStreamRenderer_TokenStreaming(t *testing.T) {
	var buf bytes.Buffer
	renderer := cli.NewStreamRenderer(&buf)

	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventTokenChunk,
		AgentName: "SystemAgent",
		TextDelta: "Hello ",
	})
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventTokenChunk,
		AgentName: "SystemAgent",
		TextDelta: "world!",
	})
	renderer.Flush()

	out := buf.String()
	if !strings.Contains(out, "Hello world!") {
		t.Fatalf("expected streamed output 'Hello world!', got %q", out)
	}
}

func TestStreamRenderer_InterleavedLogsAndTokens(t *testing.T) {
	var buf bytes.Buffer
	renderer := cli.NewStreamRenderer(&buf)

	// 1. Status log
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventStatusUpdate,
		AgentName: "Manager",
		StatusMsg: "Decomposing user request...",
	})

	// 2. Tool call
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventToolCall,
		AgentName: "SystemAgent",
		ToolCall: &gateway.ToolCallInfo{
			CallID:   "call_1",
			ToolName: "sys_exec",
			ArgsJSON: `{"cmd":"ls -la"}`,
		},
	})

	// 3. Tool result
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventToolResult,
		AgentName: "SystemAgent",
		ToolResult: &gateway.ToolResultInfo{
			CallID:     "call_1",
			ToolName:   "sys_exec",
			ExitCode:   0,
			Output:     "file1.go\nfile2.go",
			DurationMs: 42,
		},
	})

	// 4. Token streaming begins
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventTokenChunk,
		AgentName: "SystemAgent",
		TextDelta: "I found 2 files: ",
	})
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventTokenChunk,
		AgentName: "SystemAgent",
		TextDelta: "file1.go and file2.go.",
	})

	// 5. Subsequent status log should cleanly break line without corrupting tokens
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventStatusUpdate,
		AgentName: "Scheduler",
		StatusMsg: "Subtask completed successfully.",
	})

	// 6. Turn complete
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventTurnComplete,
		AgentName: "Orchestrator",
		Metrics: &gateway.TurnMetrics{
			ModelName:        "claude-3-7-sonnet",
			PromptTokens:     100,
			CompletionTokens: 50,
			TotalDurationMs:  1200,
		},
	})
	renderer.Flush()

	out := buf.String()

	// Verify all components rendered clearly in harness style
	if !strings.Contains(out, "Decomposing user request") {
		t.Errorf("missing status update in output: %s", out)
	}
	if !strings.Contains(out, "Tool Call: sys_exec") {
		t.Errorf("missing tool call in output: %s", out)
	}
	if !strings.Contains(out, "cmd: ls -la") {
		t.Errorf("missing tool args in output: %s", out)
	}
	if !strings.Contains(out, "sys_exec completed (42ms)") {
		t.Errorf("missing tool result in output: %s", out)
	}
	if !strings.Contains(out, "I found 2 files: file1.go and file2.go.") {
		t.Errorf("missing streamed tokens in output: %s", out)
	}
	if !strings.Contains(out, "Model: claude-3-7-sonnet") {
		t.Errorf("missing telemetry metrics in output: %s", out)
	}
}

func TestStreamRenderer_HeartbeatSuppressionDuringTokens(t *testing.T) {
	var buf bytes.Buffer
	renderer := cli.NewStreamRenderer(&buf)

	// Stream a token chunk that does not end with a newline
	renderer.RenderEvent(gateway.OutboundEvent{
		Type:      gateway.EventTokenChunk,
		AgentName: "SystemAgent",
		TextDelta: "Generating response text...",
	})

	// Attempt heartbeat while token stream is active
	renderer.RenderHeartbeat(3 * time.Second)

	out := buf.String()
	if strings.Contains(out, "Still processing") {
		t.Fatalf("heartbeat should be suppressed during active token stream, but found in output: %s", out)
	}

	// Flush and verify heartbeat is allowed when idle
	renderer.Flush()
	buf.Reset()
	renderer.RenderHeartbeat(3 * time.Second)
	if !strings.Contains(buf.String(), "Still processing") {
		t.Fatalf("expected heartbeat when idle, got: %s", buf.String())
	}
}

func TestRenderer_RenderToolResult_Error(t *testing.T) {
	res := cli.RenderToolResult("SystemAgent", "sys_exec", 1, "command not found: foobar", "", 85, true)
	if !strings.Contains(res, "sys_exec failed (85ms, exit code 1)") {
		t.Fatalf("expected error line, got: %s", res)
	}
	if !strings.Contains(res, "command not found: foobar") {
		t.Fatalf("expected error output preview, got: %s", res)
	}
}

func TestRenderer_RenderToolResult_Spillover(t *testing.T) {
	res := cli.RenderToolResult("SystemAgent", "sys_exec", 0, "truncated...", "workspace/artifacts/out.txt", 150, false)
	if !strings.Contains(res, "Spilled to artifact: workspace/artifacts/out.txt") {
		t.Fatalf("expected artifact spillover line, got: %s", res)
	}
}

func TestTurnHandle_ToolCallStreaming(t *testing.T) {
	handle := supervisor.NewTurnHandle("sess_t", "turn_t")

	handle.PushToolCall(protocol.ToolCallPayload{
		CallID:   "call_abc",
		ToolName: "sys_exec",
		Arguments: map[string]any{
			"cmd": "pwd",
		},
	})

	handle.PushToolResult(protocol.ToolResultPayload{
		CallID:     "call_abc",
		ToolName:   "sys_exec",
		ExitCode:   0,
		Output:     "/home/user",
		DurationMs: 15,
	})

	select {
	case tc := <-handle.ToolCalls():
		if tc.ToolName != "sys_exec" || tc.CallID != "call_abc" {
			t.Errorf("unexpected tool call: %+v", tc)
		}
	default:
		t.Fatal("expected tool call to be available")
	}

	select {
	case tr := <-handle.ToolResults():
		if tr.ToolName != "sys_exec" || tr.DurationMs != 15 {
			t.Errorf("unexpected tool result: %+v", tr)
		}
	default:
		t.Fatal("expected tool result to be available")
	}

	handle.Finish(nil)

	// Ensure channels are closed
	_, ok := <-handle.ToolCalls()
	if ok {
		t.Fatal("expected ToolCalls channel to be closed after Finish")
	}
	_, ok = <-handle.ToolResults()
	if ok {
		t.Fatal("expected ToolResults channel to be closed after Finish")
	}
}

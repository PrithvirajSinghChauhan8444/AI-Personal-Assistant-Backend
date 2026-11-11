package bridge_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"assistant/src/bridge/protocol"
	"assistant/src/bridge/supervisor"
	"assistant/src/tools"
	"assistant/src/tools/tools/sys"
)

func TestLiveBridgeE2ERoundtrip(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping e2e live bridge test in short mode")
	}

	reg := tools.NewToolRegistry(nil, nil)
	_ = reg.Register(sys.NewSysExecTool())

	cfg := supervisor.Config{
		ProcessConfig: supervisor.ProcessConfig{
			PythonBinary: "", // auto-discovered from .venv
			ModulePath:   "src.bridge.daemon",
		},
		ToolExecutor: reg,
		ReadyTimeout: 10 * time.Second,
		GracePeriod:  3 * time.Second,
	}

	sup := supervisor.NewSupervisor(cfg)

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// 1. Verify Start and Ready Handshake over anonymous pipes
	if err := sup.Start(ctx); err != nil {
		t.Fatalf("failed to start supervisor: %v", err)
	}

	if !sup.IsRunning() {
		t.Fatal("expected supervisor to report running state")
	}

	// 2. Test turn execution with token and thought streaming
	sessionID := "e2e_sess"
	turnID1 := "turn_stream_1"
	payload1 := &protocol.StartTurnPayload{
		TargetAgent: "echo",
		Prompt:      "ping_pong_hello",
	}

	handle1, err := sup.StartTurn(ctx, sessionID, turnID1, payload1)
	if err != nil {
		t.Fatalf("failed to start turn 1: %v", err)
	}

	var thoughts []string
	go func() {
		for th := range handle1.Thoughts() {
			thoughts = append(thoughts, th)
		}
	}()

	var tokens string
	for tok := range handle1.Tokens() {
		tokens += tok
	}

	select {
	case err := <-handle1.Errors():
		if err != nil {
			t.Fatalf("turn 1 encountered error: %v", err)
		}
	case comp := <-handle1.Complete():
		if comp == nil || comp.Status != "success" {
			t.Fatalf("expected turn 1 success, got %v", comp)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for turn 1 completion")
	}

	if !strings.Contains(tokens, "ping_pong_hello") {
		t.Errorf("expected streamed tokens to contain 'ping_pong_hello', got %q", tokens)
	}

	// 3. Test Tool Call roundtrip (Python -> Go Layer 3 Tool Engine -> Python -> Go)
	turnID2 := "turn_tool_2"
	payload2 := &protocol.StartTurnPayload{
		TargetAgent: "echo",
		Prompt:      `call_tool:sys_exec:{"command":"echo live_bridge_tool_ok"}`,
	}

	handle2, err := sup.StartTurn(ctx, sessionID, turnID2, payload2)
	if err != nil {
		t.Fatalf("failed to start turn 2: %v", err)
	}

	var toolTokens string
	for tok := range handle2.Tokens() {
		toolTokens += tok
	}

	select {
	case comp := <-handle2.Complete():
		if comp == nil || comp.Status != "success" {
			t.Fatalf("expected turn 2 success, got %v", comp)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for turn 2 tool roundtrip")
	}

	if !strings.Contains(toolTokens, "live_bridge_tool_ok") {
		t.Errorf("expected tool output to contain 'live_bridge_tool_ok', got %q", toolTokens)
	}

	// 4. Test Clean Process Termination (Zero-Zombie Guarantee)
	if err := sup.Stop(); err != nil {
		t.Fatalf("failed to cleanly stop supervisor: %v", err)
	}

	if sup.IsRunning() {
		t.Fatal("expected supervisor to not be running after Stop()")
	}
}

func TestLiveBridgeMultiTurnSequential(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping e2e live bridge test in short mode")
	}

	reg := tools.NewToolRegistry(nil, nil)
	_ = reg.Register(sys.NewSysExecTool())

	cfg := supervisor.Config{
		ProcessConfig: supervisor.ProcessConfig{
			PythonBinary: "",
			ModulePath:   "src.bridge.daemon",
		},
		ToolExecutor: reg,
		ReadyTimeout: 10 * time.Second,
		GracePeriod:  3 * time.Second,
	}

	sup := supervisor.NewSupervisor(cfg)
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	if err := sup.Start(ctx); err != nil {
		t.Fatalf("failed to start supervisor: %v", err)
	}
	defer func() { _ = sup.Stop() }()

	sessionID := "seq_sess"

	// Turn 1: Echo greeting
	h1, err := sup.StartTurn(ctx, sessionID, "turn_seq_1", &protocol.StartTurnPayload{
		TargetAgent: "echo",
		Prompt:      "seq_step_one",
	})
	if err != nil {
		t.Fatalf("turn 1 failed: %v", err)
	}
	var tok1 string
	for tok := range h1.Tokens() {
		tok1 += tok
	}
	<-h1.Complete()
	if !strings.Contains(tok1, "seq_step_one") {
		t.Errorf("turn 1 token mismatch: %q", tok1)
	}

	// Turn 2: Tool execution
	h2, err := sup.StartTurn(ctx, sessionID, "turn_seq_2", &protocol.StartTurnPayload{
		TargetAgent: "echo",
		Prompt:      `call_tool:sys_exec:{"command":"echo seq_tool_ok"}`,
	})
	if err != nil {
		t.Fatalf("turn 2 failed: %v", err)
	}
	var tok2 string
	for tok := range h2.Tokens() {
		tok2 += tok
	}
	<-h2.Complete()
	if !strings.Contains(tok2, "seq_tool_ok") {
		t.Errorf("turn 2 tool token mismatch: %q", tok2)
	}

	// Turn 3: Follow-up echo to confirm supervisor health after tool call
	h3, err := sup.StartTurn(ctx, sessionID, "turn_seq_3", &protocol.StartTurnPayload{
		TargetAgent: "echo",
		Prompt:      "seq_step_three_healthy",
	})
	if err != nil {
		t.Fatalf("turn 3 failed: %v", err)
	}
	var tok3 string
	for tok := range h3.Tokens() {
		tok3 += tok
	}
	<-h3.Complete()
	if !strings.Contains(tok3, "seq_step_three_healthy") {
		t.Errorf("turn 3 token mismatch: %q", tok3)
	}
}

func TestLiveBridgeTurnCancellation(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping e2e live bridge test in short mode")
	}

	cfg := supervisor.Config{
		ProcessConfig: supervisor.ProcessConfig{
			PythonBinary: "",
			ModulePath:   "src.bridge.daemon",
		},
		ReadyTimeout: 10 * time.Second,
		GracePeriod:  3 * time.Second,
	}

	sup := supervisor.NewSupervisor(cfg)
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := sup.Start(ctx); err != nil {
		t.Fatalf("failed to start supervisor: %v", err)
	}
	defer func() { _ = sup.Stop() }()

	turnCtx, turnCancel := context.WithCancel(ctx)
	handle, err := sup.StartTurn(turnCtx, "sess_cancel", "turn_cancel_1", &protocol.StartTurnPayload{
		TargetAgent: "echo",
		Prompt:      "will_be_cancelled",
	})
	if err != nil {
		t.Fatalf("failed to start turn: %v", err)
	}

	// Immediately cancel context
	turnCancel()

	// Drain channels or wait for errors/cancellation
	select {
	case err := <-handle.Errors():
		if err == nil {
			t.Fatal("expected error on cancelled turn handle")
		}
	case comp := <-handle.Complete():
		if comp != nil && comp.Status != "cancelled" && comp.Status != "success" {
			t.Logf("turn completed with: %v", comp)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("timed out waiting for turn cancellation resolution")
	}

	// Verify supervisor remains fully operational after cancellation
	hPost, err := sup.StartTurn(ctx, "sess_cancel", "turn_post_cancel", &protocol.StartTurnPayload{
		TargetAgent: "echo",
		Prompt:      "post_cancel_ping",
	})
	if err != nil {
		t.Fatalf("failed to start turn post-cancellation: %v", err)
	}

	var postTok string
	for tok := range hPost.Tokens() {
		postTok += tok
	}
	<-hPost.Complete()
	if !strings.Contains(postTok, "post_cancel_ping") {
		t.Errorf("expected post-cancel ping tokens, got %q", postTok)
	}
}

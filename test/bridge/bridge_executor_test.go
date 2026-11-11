package bridge_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"assistant/src/bridge/supervisor"
	"assistant/src/gateway"
	"assistant/src/orchestrator"
	"assistant/src/orchestrator/router"
	"assistant/src/tools"
	"assistant/src/tools/tools/sys"
)

func TestBridgeTurnExecutor_NotRunning(t *testing.T) {
	t.Parallel()

	exec := orchestrator.NewBridgeTurnExecutor(nil)
	eventCh := make(chan gateway.OutboundEvent, 5)

	input := orchestrator.TurnExecutionInput{
		SessionID: "sess_not_running",
		TurnID:    "turn_not_running",
		Prompt:    "hello",
	}

	err := exec.Execute(context.Background(), input, eventCh)
	if err == nil {
		t.Fatal("expected error when supervisor is nil/not running, got nil")
	}
}

func TestBridgeTurnExecutor_LiveExecution(t *testing.T) {
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
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := sup.Start(ctx); err != nil {
		t.Fatalf("failed to start supervisor: %v", err)
	}
	defer func() { _ = sup.Stop() }()

	bridgeExec := orchestrator.NewBridgeTurnExecutor(sup)
	eventCh := make(chan gateway.OutboundEvent, 20)

	input := orchestrator.TurnExecutionInput{
		SessionID: "sess_orch_bridge",
		TurnID:    "turn_orch_bridge_1",
		TraceID:   "tr_orch_bridge_1",
		Decision: router.RouteDecision{
			Type:        router.RouteFastPath,
			TargetAgent: "echo",
			Prompt:      "hello_from_orchestrator_via_bridge",
		},
		Prompt: "hello_from_orchestrator_via_bridge",
	}

	execErrCh := make(chan error, 1)
	go func() {
		execErrCh <- bridgeExec.Execute(ctx, input, eventCh)
		close(eventCh)
	}()

	var receivedTokens strings.Builder
	var receivedThoughts int
	var completedReceived bool

	for ev := range eventCh {
		t.Logf("Received event: type=%s, delta=%q, error=%v", ev.Type, ev.TextDelta, ev.Error)
		switch ev.Type {
		case gateway.EventTokenChunk:
			receivedTokens.WriteString(ev.TextDelta)
		case gateway.EventThoughtChunk:
			receivedThoughts++
		case gateway.EventTurnComplete:
			completedReceived = true
		}
	}

	if err := <-execErrCh; err != nil {
		t.Fatalf("BridgeTurnExecutor returned error: %v", err)
	}

	if !strings.Contains(receivedTokens.String(), "hello_from_orchestrator_via_bridge") {
		t.Errorf("expected received tokens to contain prompt, got %q", receivedTokens.String())
	}
	if !completedReceived {
		t.Error("expected EventTurnComplete event to be received")
	}
}

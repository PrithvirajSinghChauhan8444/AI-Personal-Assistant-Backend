package orchestrator_test

import (
	"context"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"assistant/src/bridge/supervisor"
	"assistant/src/gateway"
	"assistant/src/orchestrator"
	"assistant/src/orchestrator/planner"
	"assistant/src/orchestrator/safety"
	"assistant/src/orchestrator/session"
	"assistant/src/tools"
	"assistant/src/tools/tools/sys"
)

type mockEchoLLM struct{}

func (m *mockEchoLLM) Generate(ctx context.Context, systemPrompt, userPrompt string) (string, error) {
	return `{"plan_id":"plan_test","primary_goal":"echo test","subtasks":[{"id":"task_1","assigned_worker":"echo","description":"echo_bridge_test"}]}`, nil
}

func TestOrchestrator_BridgeTurnExecutor_Integration(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping live bridge integration test in short mode")
	}

	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "test_sessions.db")
	artifactsDir := filepath.Join(tempDir, "artifacts")

	store, err := session.NewSQLiteStore(dbPath)
	if err != nil {
		t.Fatalf("failed to init session store: %v", err)
	}
	defer store.Close()

	reg := tools.NewToolRegistry(nil, nil)
	_ = reg.Register(sys.NewSysExecTool())

	supCfg := supervisor.Config{
		ProcessConfig: supervisor.ProcessConfig{
			PythonBinary: "",
			ModulePath:   "src.bridge.daemon",
		},
		ToolExecutor: reg,
		ReadyTimeout: 10 * time.Second,
		GracePeriod:  3 * time.Second,
	}

	sup := supervisor.NewSupervisor(supCfg)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := sup.Start(ctx); err != nil {
		t.Fatalf("failed to start bridge supervisor: %v", err)
	}
	defer func() { _ = sup.Stop() }()

	bridgeExec := orchestrator.NewBridgeTurnExecutor(sup)

	gk := safety.NewGatekeeper()
	gk.RegisterPolicy(safety.ToolPolicy{
		ToolName: "echo",
		Risk:     safety.RiskLow,
	})
	echoWorkers := []planner.WorkerCapability{
		{Name: "echo", Description: "Echo test worker"},
	}
	mgr := planner.NewManagerAgent(&mockEchoLLM{}, echoWorkers, "")

	orch, err := orchestrator.New(orchestrator.Config{
		Store:        store,
		Gatekeeper:   gk,
		Manager:      mgr,
		Executor:     bridgeExec,
		ArtifactsDir: artifactsDir,
	})
	if err != nil {
		t.Fatalf("failed to initialize orchestrator: %v", err)
	}

	gw, err := gateway.NewGateway(orch)
	if err != nil {
		t.Fatalf("failed to initialize gateway: %v", err)
	}

	req := gateway.InboundTurnRequest{
		SessionID: "sess_bridge_integ",
		Channel:   gateway.ClientTypeCLI,
		Trigger:   gateway.TriggerInteractive,
		Prompt:    "hello echo bridge test",
	}

	eventCh, _, err := gw.SubmitTurn(ctx, req)
	if err != nil {
		t.Fatalf("SubmitTurn failed: %v", err)
	}

	var output strings.Builder
	var completed bool

	for ev := range eventCh {
		t.Logf("Event: type=%s, agent=%s, delta=%q, status=%q, error=%q, metrics=%+v", ev.Type, ev.AgentName, ev.TextDelta, ev.StatusMsg, ev.Error, ev.Metrics)
		if ev.Type == gateway.EventTokenChunk {
			output.WriteString(ev.TextDelta)
		}
		if ev.Type == gateway.EventTurnComplete && ev.Metrics != nil {
			completed = true
		}
	}

	if !completed {
		t.Fatal("expected turn to complete with metrics")
	}

	if !strings.Contains(output.String(), "echo_bridge_test") {
		t.Fatalf("expected output to contain 'echo_bridge_test', got %q", output.String())
	}
}

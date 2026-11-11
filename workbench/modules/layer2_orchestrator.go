package modules

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"

	"assistant/src/gateway"
	"assistant/src/orchestrator"
	"assistant/src/orchestrator/safety"
	"assistant/src/orchestrator/session"
	"assistant/workbench/engine"

	"github.com/google/uuid"
)

// buildOrchestrator creates a live Orchestrator instance for workbench testing.
func buildOrchestrator() (*orchestrator.Orchestrator, func(), error) {
	dataDir := filepath.Join("workspace", "workbench", "data")
	_ = os.MkdirAll(dataDir, 0755)
	artifactsDir := filepath.Join("workspace", "workbench", "artifacts")
	_ = os.MkdirAll(artifactsDir, 0755)

	dbPath := filepath.Join(dataDir, "orchestrator_sessions.db")
	store, err := session.NewSQLiteStore(dbPath)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to open session store: %w", err)
	}

	gk := safety.NewGatekeeper()
	policyPath := filepath.Join("config", "safety_policies.json")
	if _, err := os.Stat(policyPath); err == nil {
		_ = gk.LoadPoliciesFromFile(policyPath)
	}

	orch, err := orchestrator.New(orchestrator.Config{
		Store:        store,
		Gatekeeper:   gk,
		ArtifactsDir: artifactsDir,
	})
	if err != nil {
		store.Close()
		return nil, nil, fmt.Errorf("failed to initialize orchestrator: %w", err)
	}

	cleanup := func() {
		store.Close()
	}

	return orch, cleanup, nil
}

// RegisterLayer2Orchestrator registers Layer 2 Orchestrator modules.
func RegisterLayer2Orchestrator(r *engine.Registry, sup *engine.Supervisor) {
	r.Register(engine.Module{
		ID:          "l2_orchestrator_execute_turn",
		Name:        "Layer 2: Orchestrator (ExecuteTurn - Isolated)",
		Category:    "Isolated Module",
		Description: "Feeds an InboundTurnRequest directly into Layer 2 Orchestrator.ExecuteTurn, bypassing Layer 1 normalization.",
		InputType:   reflect.TypeOf(gateway.InboundTurnRequest{}),
		Presets: []engine.Preset{
			{
				ID:          "orch_happy_path",
				Name:        "Orchestrator Turn: System Query",
				Category:    "Happy Path",
				Description: "Standard turn passed directly into the Orchestrator.",
				Payload: gateway.InboundTurnRequest{
					SessionID: uuid.New().String(),
					UserID:    "local:prit",
					Channel:   gateway.ClientTypeCLI,
					Trigger:   gateway.TriggerInteractive,
					Prompt:    "Summarize available tool capabilities",
				},
			},
			{
				ID:          "orch_autonomous",
				Name:        "Autonomous Background Trigger",
				Category:    "Autonomous",
				Description: "Autonomous background trigger with restricted capabilities.",
				Payload: gateway.InboundTurnRequest{
					SessionID:           uuid.New().String(),
					UserID:              "daemon:monitor",
					Channel:             gateway.ClientTypeInternal,
					Trigger:             gateway.TriggerAutonomous,
					AllowedCapabilities: []string{"fs_read", "sys_info"},
					Prompt:              "Check system health status",
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var req gateway.InboundTurnRequest
			if err := json.Unmarshal(inputRaw, &req); err != nil {
				return nil, fmt.Errorf("invalid json for InboundTurnRequest: %w", err)
			}

			orch, cleanup, err := buildOrchestrator()
			if err != nil {
				return nil, err
			}
			defer cleanup()

			engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
				Level:   "INFO",
				Source:  "orchestrator",
				Message: fmt.Sprintf("Executing turn in Layer 2 Orchestrator for session %s (prompt: %q)", req.SessionID, req.Prompt),
			})

			eventCh := make(chan gateway.OutboundEvent, 64)
			doneCh := make(chan error, 1)

			go func() {
				doneCh <- orch.ExecuteTurn(ctx, req, eventCh)
				close(eventCh)
			}()

			for ev := range eventCh {
				var payload any = ev.TextDelta
				if ev.StatusMsg != "" {
					payload = ev.StatusMsg
				} else if ev.HITL != nil {
					payload = ev.HITL
				} else if ev.Metrics != nil {
					payload = ev.Metrics
				} else if ev.Error != "" {
					payload = ev.Error
				}

				stream <- engine.StreamEvent{
					Type:      string(ev.Type),
					AgentName: ev.AgentName,
					Payload:   payload,
				}
			}

			turnErr := <-doneCh
			return map[string]any{
				"session_id": req.SessionID,
				"status":     "ORCHESTRATOR_EXECUTION_COMPLETED",
			}, turnErr
		},
	})
}

package modules

import (
	"context"
	"encoding/json"
	"fmt"
	"reflect"

	"assistant/src/gateway"
	"assistant/workbench/engine"

	"github.com/google/uuid"
)

// RegisterE2EPipeline registers end-to-end multi-layer pipeline modules.
func RegisterE2EPipeline(r *engine.Registry, sup *engine.Supervisor) {
	r.Register(engine.Module{
		ID:          "pipeline_l1_l2_e2e",
		Name:        "Pipeline: Layer 1 Gateway -> Layer 2 Orchestrator",
		Category:    "Pipeline",
		Description: "Runs the complete live pipeline: Ingress validation & normalization (Layer 1) wired directly to Planner, Safety Gatekeeper, and SQLite Session Store (Layer 2).",
		InputType:   reflect.TypeOf(gateway.InboundTurnRequest{}),
		Presets: []engine.Preset{
			{
				ID:          "e2e_full_turn",
				Name:        "Full Pipeline: Interactive Query",
				Category:    "Happy Path",
				Description: "Submits through Gateway to live Orchestrator and captures live event stream.",
				Payload: gateway.InboundTurnRequest{
					SessionID: uuid.New().String(),
					UserID:    "local:prit",
					Channel:   gateway.ClientTypeCLI,
					Trigger:   gateway.TriggerInteractive,
					Prompt:    "List active tasks and summarize status",
				},
			},
			{
				ID:          "e2e_agent_routing",
				Name:        "Full Pipeline: Agent Target @system",
				Category:    "Agent Targeting",
				Description: "Tests prefix extraction in Gateway and routing in Orchestrator.",
				Payload: gateway.InboundTurnRequest{
					SessionID: uuid.New().String(),
					Channel:   gateway.ClientTypeCLI,
					Trigger:   gateway.TriggerInteractive,
					Prompt:    "@system check memory usage",
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var rawReq gateway.InboundTurnRequest
			if err := json.Unmarshal(inputRaw, &rawReq); err != nil {
				return nil, fmt.Errorf("invalid json: %w", err)
			}

			orch, cleanup, err := buildOrchestrator()
			if err != nil {
				return nil, err
			}
			defer cleanup()

			gw, err := gateway.NewGateway(orch)
			if err != nil {
				return nil, err
			}

			engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
				Level:   "INFO",
				Source:  "pipeline.e2e",
				Message: fmt.Sprintf("Pipeline ingress turn submitted (prompt: %q)", rawReq.Prompt),
			})

			eventCh, normalizedReq, err := gw.SubmitTurn(ctx, rawReq)
			if err != nil {
				return nil, err
			}

			stream <- engine.StreamEvent{
				Type:      "GATEWAY_NORMALIZED",
				AgentName: "Gateway",
				Payload:   normalizedReq,
			}

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

			return map[string]any{
				"normalized_request": normalizedReq,
				"status":             "PIPELINE_TURN_COMPLETED",
			}, nil
		},
	})
}

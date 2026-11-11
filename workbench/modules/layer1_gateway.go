package modules

import (
	"context"
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"time"

	"assistant/src/gateway"
	"assistant/workbench/engine"

	"github.com/google/uuid"
)

// MockTurnHandler implements gateway.TurnHandler for isolated Layer 1 testing.
type MockTurnHandler struct {
	supervisor *engine.Supervisor
}

func (m *MockTurnHandler) ExecuteTurn(ctx context.Context, req gateway.InboundTurnRequest, eventCh chan<- gateway.OutboundEvent) error {
	// Emit Initial Status
	select {
	case <-ctx.Done():
		return ctx.Err()
	case eventCh <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: "MockOrchestrator",
		StatusMsg: fmt.Sprintf("Turn received for session %s. Processing prompt...", req.SessionID),
	}:
	}

	// Check for HITL trigger in prompt
	if strings.Contains(strings.ToLower(req.Prompt), "delete") ||
		strings.Contains(strings.ToLower(req.Prompt), "drop") ||
		strings.Contains(strings.ToLower(req.Prompt), "hitl") {

		reqID := uuid.New().String()
		hitlCh := make(chan gateway.HITLResponse, 1)
		if m.supervisor != nil {
			m.supervisor.RegisterHITL(reqID, hitlCh)
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case eventCh <- gateway.OutboundEvent{
			SessionID: req.SessionID,
			TraceID:   req.TraceID,
			Type:      gateway.EventHITLRequest,
			AgentName: "Gatekeeper",
			HITL: &gateway.HITLApprovalPrompt{
				RequestID:        reqID,
				ToolName:         "sys_delete_file",
				Reason:           "Execution requires explicit human authorization for high-risk action.",
				ArgumentsJSON:    `{"path":"/important/system.conf","force":true}`,
				AvailableChoices: []string{"Approve", "Deny"},
			},
		}:
		}

		// Wait for HITL response or context abort
		select {
		case <-ctx.Done():
			return ctx.Err()
		case resp := <-hitlCh:
			decision := "REJECTED"
			if resp.Approved {
				decision = "APPROVED"
			}
			eventCh <- gateway.OutboundEvent{
				SessionID: req.SessionID,
				TraceID:   req.TraceID,
				Type:      gateway.EventStatusUpdate,
				AgentName: "Gatekeeper",
				StatusMsg: fmt.Sprintf("HITL Decision: %s (User feedback: %q)", decision, resp.UserFeedback),
			}
		case <-time.After(30 * time.Second):
			return fmt.Errorf("hitl approval timed out after 30s")
		}
	}

	// Stream Simulated Reasoning Thought Chunks
	select {
	case <-ctx.Done():
		return ctx.Err()
	case eventCh <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventThoughtChunk,
		AgentName: "ManagerAgent",
		TextDelta: fmt.Sprintf("Analyzing normalized request from channel %s with trigger %s. Intent classification complete.", req.Channel, req.Trigger),
	}:
	}

	time.Sleep(150 * time.Millisecond)

	// Stream Simulated Token Chunks
	tokens := []string{
		"Hello! ", "I am ", "the Assistant. ", "I received ", "your prompt: ",
		fmt.Sprintf("%q. ", req.Prompt), "Executing smoothly across ", "isolated gateway boundary.",
	}

	for _, token := range tokens {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case eventCh <- gateway.OutboundEvent{
			SessionID: req.SessionID,
			TraceID:   req.TraceID,
			Type:      gateway.EventTokenChunk,
			AgentName: "Assistant",
			TextDelta: token,
		}:
		}
		time.Sleep(50 * time.Millisecond)
	}

	// Stream Turn Complete with Telemetry
	select {
	case <-ctx.Done():
		return ctx.Err()
	case eventCh <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventTurnComplete,
		AgentName: "Orchestrator",
		Metrics: &gateway.TurnMetrics{
			ModelName:         "mock-gemini-3.8-flash",
			PromptTokens:      42,
			CompletionTokens:  18,
			CachedTokens:      12,
			TimeToFirstByteMs: 150,
			TotalDurationMs:   550,
		},
	}:
	}

	return nil
}

func (m *MockTurnHandler) SubmitHITLResponse(ctx context.Context, resp gateway.HITLResponse) error {
	if m.supervisor != nil {
		if m.supervisor.SubmitHITL(resp) {
			return nil
		}
	}
	return fmt.Errorf("no pending HITL approval for request_id: %s", resp.RequestID)
}

// RegisterLayer1Gateway registers Layer 1 Gateway endpoints into the registry.
func RegisterLayer1Gateway(r *engine.Registry, sup *engine.Supervisor) {
	// 1. SubmitTurn (Isolated)
	r.Register(engine.Module{
		ID:          "l1_gateway_submit_turn",
		Name:        "Layer 1: Gateway (SubmitTurn - Isolated)",
		Category:    "Isolated Module",
		Description: "Feeds an InboundTurnRequest directly into Gateway.SubmitTurn, normalizes it, and streams OutboundEvents from an isolated handler.",
		InputType:   reflect.TypeOf(gateway.InboundTurnRequest{}),
		Presets: []engine.Preset{
			{
				ID:          "happy_path",
				Name:        "Happy Path (Standard Turn)",
				Category:    "Happy Path",
				Description: "Valid CLI interactive turn request with UUID session.",
				Payload: gateway.InboundTurnRequest{
					SessionID: uuid.New().String(),
					UserID:    "local:prit",
					Channel:   gateway.ClientTypeCLI,
					Trigger:   gateway.TriggerInteractive,
					Prompt:    "Show disk usage in workspace",
				},
			},
			{
				ID:          "agent_targeting",
				Name:        "Agent Targeting (@browser)",
				Category:    "Agent Targeting",
				Description: "Prompt with explicit agent targeting that normalizer extracts.",
				Payload: gateway.InboundTurnRequest{
					SessionID: uuid.New().String(),
					Channel:   gateway.ClientTypeCLI,
					Trigger:   gateway.TriggerInteractive,
					Prompt:    "@browser search for latest Go release notes",
				},
			},
			{
				ID:          "empty_malformed",
				Name:        "Boundary: Empty / Whitespace",
				Category:    "Edge Case",
				Description: "Empty prompt to test gateway error rejection.",
				Payload: gateway.InboundTurnRequest{
					Channel: gateway.ClientTypeCLI,
					Prompt:  "   ",
				},
			},
			{
				ID:          "security_attack",
				Name:        "Security: Path Traversal Session",
				Category:    "Security",
				Description: "Attempt to pass path traversal characters in session ID.",
				Payload: gateway.InboundTurnRequest{
					SessionID: "../../etc/shadow",
					Channel:   gateway.ClientTypeCLI,
					Prompt:    "List files",
				},
			},
			{
				ID:          "autonomous_violation",
				Name:        "Violation: Autonomous Mode + Wildcard",
				Category:    "Violation",
				Description: "Autonomous trigger with invalid wildcard capabilities.",
				Payload: gateway.InboundTurnRequest{
					SessionID:           uuid.New().String(),
					Trigger:             gateway.TriggerAutonomous,
					AllowedCapabilities: []string{"*"},
					Prompt:              "Run system cleanup",
				},
			},
			{
				ID:          "hitl_trigger",
				Name:        "HITL: Trigger Human In The Loop",
				Category:    "HITL",
				Description: "Triggers a high-risk tool simulation awaiting user Approve/Deny.",
				Payload: gateway.InboundTurnRequest{
					SessionID: uuid.New().String(),
					Channel:   gateway.ClientTypeCLI,
					Trigger:   gateway.TriggerInteractive,
					Prompt:    "Delete /important/system.conf and drop databases",
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var req gateway.InboundTurnRequest
			if err := json.Unmarshal(inputRaw, &req); err != nil {
				return nil, fmt.Errorf("invalid json for InboundTurnRequest: %w", err)
			}

			mockHandler := &MockTurnHandler{supervisor: sup}
			gw, err := gateway.NewGateway(mockHandler)
			if err != nil {
				return nil, err
			}

			eventCh, normalizedReq, err := gw.SubmitTurn(ctx, req)
			if err != nil {
				engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
					Level:   "WARN",
					Source:  "gateway",
					Message: fmt.Sprintf("Gateway normalization/submission failed: %v", err),
				})
				return nil, err
			}

			engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
				Level:   "INFO",
				Source:  "gateway",
				Message: fmt.Sprintf("SubmitTurn accepted: session_id=%s, channel=%s, prompt_len=%d", normalizedReq.SessionID, normalizedReq.Channel, len(normalizedReq.Prompt)),
				Fields: map[string]any{
					"session_id": normalizedReq.SessionID,
					"channel":    normalizedReq.Channel,
					"trigger":    normalizedReq.Trigger,
				},
			})

			// Multiplex eventCh to workbench stream
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
				"status":             "TURN_STREAM_FINISHED",
			}, nil
		},
	})

	// 2. NormalizeInbound (Direct Function)
	r.Register(engine.Module{
		ID:          "l1_gateway_normalize_inbound",
		Name:        "Layer 1: Gateway (NormalizeInbound)",
		Category:    "Isolated Module",
		Description: "Tests direct Layer 1 input normalization, agent prefix extraction (@agent), UUID defaults, and capability validation.",
		InputType:   reflect.TypeOf(gateway.InboundTurnRequest{}),
		Presets: []engine.Preset{
			{
				ID:       "agent_routing_prefix",
				Name:     "Agent Routing Prefix (@system)",
				Category: "Agent Targeting",
				Payload: gateway.InboundTurnRequest{
					Prompt:  "@system check server uptime",
					Channel: gateway.ClientTypeCLI,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var raw gateway.InboundTurnRequest
			if err := json.Unmarshal(inputRaw, &raw); err != nil {
				return nil, err
			}

			normalized, err := gateway.NormalizeInbound(raw)
			if err != nil {
				return nil, err
			}

			return normalized, nil
		},
	})
}

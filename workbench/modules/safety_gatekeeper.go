package modules

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"

	"assistant/src/gateway"
	"assistant/src/orchestrator/safety"
	"assistant/workbench/engine"
)

// SafetyEvaluateInput defines the schema for testing the Gatekeeper module directly.
type SafetyEvaluateInput struct {
	ToolName            string              `json:"tool_name" desc:"Name of tool to evaluate (e.g. fs_read, sys_exec, fs_delete)"`
	Trigger             gateway.TriggerType `json:"trigger" enum:"INTERACTIVE,AUTONOMOUS" desc:"Execution mode: INTERACTIVE or AUTONOMOUS"`
	AllowedCapabilities []string            `json:"allowed_capabilities" desc:"List of granted capability scopes (e.g. system_exec, fs_write)"`
}

// RegisterSafetyGatekeeper registers the Safety Gatekeeper module.
func RegisterSafetyGatekeeper(r *engine.Registry) {
	r.Register(engine.Module{
		ID:          "l2_safety_gatekeeper_evaluate",
		Name:        "Layer 2: Safety Gatekeeper (Evaluate)",
		Category:    "Isolated Module",
		Description: "Evaluates tool execution security against safety policies, autonomous constraints, and required capabilities.",
		InputType:   reflect.TypeOf(SafetyEvaluateInput{}),
		Presets: []engine.Preset{
			{
				ID:          "low_risk_interactive",
				Name:        "Low Risk (fs_read, Interactive)",
				Category:    "Happy Path",
				Description: "Read-only tool allowed immediately without HITL.",
				Payload: SafetyEvaluateInput{
					ToolName:            "fs_read",
					Trigger:             gateway.TriggerInteractive,
					AllowedCapabilities: []string{"fs_read"},
				},
			},
			{
				ID:          "high_risk_hitl",
				Name:        "High Risk (fs_delete, Interactive -> Requires HITL)",
				Category:    "HITL",
				Description: "High-risk tool allowed in interactive mode, but requires human approval.",
				Payload: SafetyEvaluateInput{
					ToolName:            "fs_delete",
					Trigger:             gateway.TriggerInteractive,
					AllowedCapabilities: []string{"fs_write"},
				},
			},
			{
				ID:          "autonomous_violation",
				Name:        "Autonomous Violation (sys_exec, Autonomous -> Rejected)",
				Category:    "Violation",
				Description: "Interactive-only tool invoked in autonomous background mode is rejected.",
				Payload: SafetyEvaluateInput{
					ToolName:            "sys_exec",
					Trigger:             gateway.TriggerAutonomous,
					AllowedCapabilities: []string{"system_exec"},
				},
			},
			{
				ID:          "missing_capability",
				Name:        "Capability Violation (git_commit without git_ops)",
				Category:    "Security",
				Description: "Tool invoked without matching capability grant.",
				Payload: SafetyEvaluateInput{
					ToolName:            "git_commit",
					Trigger:             gateway.TriggerInteractive,
					AllowedCapabilities: []string{"fs_read"},
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var input SafetyEvaluateInput
			if err := json.Unmarshal(inputRaw, &input); err != nil {
				return nil, fmt.Errorf("invalid json for SafetyEvaluateInput: %w", err)
			}

			gk := safety.NewGatekeeper()
			policyPath := filepath.Join("config", "safety_policies.json")
			if _, err := os.Stat(policyPath); err == nil {
				_ = gk.LoadPoliciesFromFile(policyPath)
			}

			stream <- engine.StreamEvent{
				Type:      "STATUS_UPDATE",
				AgentName: "Gatekeeper",
				Payload:   fmt.Sprintf("Evaluating safety for tool %q under trigger %s...", input.ToolName, input.Trigger),
			}

			result := gk.Evaluate(input.ToolName, input.Trigger, input.AllowedCapabilities)

			verdict := "ALLOWED"
			if !result.Allowed {
				verdict = "DENIED"
			} else if result.RequiresHITL {
				verdict = "REQUIRES_HITL"
			}

			engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
				Level:   "INFO",
				Source:  "gatekeeper",
				Message: fmt.Sprintf("Gatekeeper evaluated tool=%q trigger=%s -> %s (risk=%s)", input.ToolName, input.Trigger, verdict, result.Risk),
				Fields: map[string]any{
					"tool":    input.ToolName,
					"trigger": input.Trigger,
					"verdict": verdict,
					"risk":    result.Risk,
				},
			})

			stream <- engine.StreamEvent{
				Type:      "POLICY_VERDICT",
				AgentName: "Gatekeeper",
				Payload: map[string]any{
					"verdict": verdict,
					"risk":    result.Risk,
					"reason":  result.Reason,
				},
			}

			return result, nil
		},
	})
}

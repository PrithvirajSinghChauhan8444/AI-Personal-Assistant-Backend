package modules

import (
	"context"
	"encoding/json"
	"fmt"
	"path/filepath"
	"reflect"
	"strings"
	"time"

	"assistant/src/bootstrap"
	"assistant/src/gateway"
	"assistant/workbench/engine"

	"github.com/google/uuid"
)

// PipelineTurnInput encapsulates inbound turn parameters for the end-to-end production stack.
type PipelineTurnInput struct {
	SessionID   string   `json:"session_id" desc:"Unique session identifier (leave empty for auto-generated UUID)"`
	UserID      string   `json:"user_id" desc:"User identifier (default: local:prit)"`
	Channel     string   `json:"channel" desc:"Ingress channel (CLI, WEB, TELEGRAM)"`
	Prompt      string   `json:"prompt" desc:"Input prompt or command for the assistant"`
	AllowedCaps []string `json:"allowed_capabilities,omitempty" desc:"Optional capability whitelist"`
	TimeoutSec  int      `json:"timeout_seconds" desc:"Maximum turn execution timeout in seconds (default: 45)"`
}

// RegisterE2EPipeline registers the complete end-to-end production pipeline powered by bootstrap/main.go.
func RegisterE2EPipeline(r *engine.Registry, sup *engine.Supervisor) {
	r.Register(engine.Module{
		ID:          "pipeline_production_e2e",
		Name:        "Pipeline: Full Production Stack (main.go End-to-End)",
		Tier:        "LAYER_BENCH",
		Layer:       "pipeline",
		Category:    "Pipeline",
		Description: "Executes the live end-to-end production stack identical to cmd/assistant/main.go: Layer 1 Gateway -> Layer 2 Orchestrator & Session Store -> Layer 3 Tool Engine -> Layer 4 IPC Bridge -> Layer 6 Specialised Agents.",
		InputType:   reflect.TypeOf(PipelineTurnInput{}),
		Presets: []engine.Preset{
			{
				ID:          "e2e_main_interactive",
				Name:        "Interactive Query (Full main.go Stack)",
				Category:    "Production Stack",
				Description: "Ingress via Gateway -> Controller -> SQLite Session Store -> Bridge -> Python Agent -> Streamed Response",
				Payload: PipelineTurnInput{
					SessionID:   "sess_e2e_prod",
					UserID:      "local:prit",
					Channel:     "CLI",
					Prompt:      "List active tasks and summarize workspace status",
					TimeoutSec:  45,
				},
			},
			{
				ID:          "e2e_main_system_agent",
				Name:        "Agent Targeting: @system (Tool Execution)",
				Category:    "Tool Execution",
				Description: "Dispatches to @system agent, runs native tools in Layer 3 via Layer 4 IPC bridge, and streams results.",
				Payload: PipelineTurnInput{
					SessionID:   "sess_e2e_system",
					UserID:      "local:prit",
					Channel:     "CLI",
					Prompt:      "@system check memory usage and list workspace files",
					TimeoutSec:  45,
				},
			},
			{
				ID:          "e2e_main_echo_fast",
				Name:        "Diagnostics: Full Stack Echo Roundtrip",
				Category:    "Diagnostics",
				Description: "Runs entire main.go pipeline with fast echo agent for high-speed verification.",
				Payload: PipelineTurnInput{
					SessionID:   "sess_e2e_echo",
					UserID:      "local:prit",
					Channel:     "CLI",
					Prompt:      "@echo Hello from live main.go production stack!",
					TimeoutSec:  20,
				},
			},
			{
				ID:          "e2e_main_research_agent",
				Name:        "Agent Targeting: @research (Repository Inspection)",
				Category:    "Research Agent",
				Description: "Dispatches to @research agent with tool engine permissions to inspect project workspace.",
				Payload: PipelineTurnInput{
					SessionID:   "sess_e2e_research",
					UserID:      "local:prit",
					Channel:     "CLI",
					Prompt:      "@research inspect current repository status and summarize changes",
					TimeoutSec:  45,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var in PipelineTurnInput
			if err := json.Unmarshal(inputRaw, &in); err != nil {
				return nil, fmt.Errorf("invalid json payload: %w", err)
			}

			if in.SessionID == "" {
				in.SessionID = "sess_" + uuid.New().String()[:8]
			}
			if in.UserID == "" {
				in.UserID = "local:prit"
			}
			if in.Channel == "" {
				in.Channel = string(gateway.ClientTypeCLI)
			}
			if in.Prompt == "" {
				in.Prompt = "Hello from the Module Workbench!"
			}
			if in.TimeoutSec <= 0 {
				in.TimeoutSec = 45
			}

			turnCtx, cancel := context.WithTimeout(ctx, time.Duration(in.TimeoutSec)*time.Second)
			defer cancel()

			engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
				Level:   "INFO",
				Source:  "pipeline.main",
				Message: fmt.Sprintf("Bootstrapping full production stack for turn (prompt: %q)", in.Prompt),
			})

			bootStart := time.Now()

			// Configure runtime stack identical to cmd/assistant/main.go
			cfg := bootstrap.LoadConfig(filepath.Join("config", "system.json"))
			cfg.WorkspaceDir = filepath.Join("workspace", "workbench")
			cfg.ArtifactsDir = filepath.Join("workspace", "workbench", "artifacts")
			cfg.DatabasePath = filepath.Join("workspace", "workbench", "data", "sessions.db")
			cfg.ConfigDir = "config"
			cfg.ReadyTimeout = 15 * time.Second
			cfg.GracePeriod = 3 * time.Second

			stack, cleanup, err := bootstrap.BuildStack(turnCtx, cfg)
			if err != nil {
				return nil, fmt.Errorf("failed to build production stack from main.go: %w", err)
			}
			defer cleanup()

			bootDurationMs := time.Since(bootStart).Milliseconds()

			stream <- engine.StreamEvent{
				Type:      "PIPELINE_BOOT_READY",
				AgentName: "ProductionStack",
				Payload: map[string]any{
					"status":             "READY",
					"boot_duration_ms":   bootDurationMs,
					"store_db":           cfg.DatabasePath,
					"artifacts_dir":      cfg.ArtifactsDir,
					"bridge_supervisor":  "Python resident daemon connected over anonymous pipes",
					"gateway":            "Layer 1 Gateway wired to Layer 2 Orchestrator",
				},
			}

			rawReq := gateway.InboundTurnRequest{
				SessionID:           in.SessionID,
				UserID:              in.UserID,
				Channel:             gateway.ClientType(strings.ToUpper(in.Channel)),
				Trigger:             gateway.TriggerInteractive,
				Prompt:              in.Prompt,
				AllowedCapabilities: in.AllowedCaps,
			}

			eventCh, normalizedReq, err := stack.Gateway.SubmitTurn(turnCtx, rawReq)
			if err != nil {
				return nil, fmt.Errorf("gateway submit turn failed: %w", err)
			}

			stream <- engine.StreamEvent{
				Type:      "GATEWAY_NORMALIZED",
				AgentName: "Gateway",
				Payload:   normalizedReq,
			}

			var thoughts []string
			var tokensBuilder strings.Builder
			var finalMetrics *gateway.TurnMetrics
			var turnError string

			for ev := range eventCh {
				var payload any = ev.TextDelta
				switch ev.Type {
				case gateway.EventThoughtChunk:
					thoughts = append(thoughts, ev.TextDelta)
					payload = ev.TextDelta
				case gateway.EventTokenChunk:
					tokensBuilder.WriteString(ev.TextDelta)
					payload = ev.TextDelta
				case gateway.EventStatusUpdate:
					payload = ev.StatusMsg
				case gateway.EventHITLRequest:
					payload = ev.HITL
				case gateway.EventTurnComplete:
					finalMetrics = ev.Metrics
					payload = ev.Metrics
				case gateway.EventTurnError:
					turnError = ev.Error
					payload = ev.Error
				}

				stream <- engine.StreamEvent{
					Type:      string(ev.Type),
					AgentName: ev.AgentName,
					Payload:   payload,
				}
			}

			if turnError != "" {
				return nil, fmt.Errorf("turn execution failed: %s", turnError)
			}

			return map[string]any{
				"status":              "PIPELINE_TURN_COMPLETED",
				"session_id":          in.SessionID,
				"normalized_request":  normalizedReq,
				"boot_duration_ms":    bootDurationMs,
				"thoughts_count":      len(thoughts),
				"accumulated_tokens":  tokensBuilder.String(),
				"metrics":             finalMetrics,
			}, nil
		},
	})
}

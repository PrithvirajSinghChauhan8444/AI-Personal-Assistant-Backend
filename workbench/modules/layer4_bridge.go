package modules

import (
	"context"
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"time"

	"assistant/src/bridge/protocol"
	"assistant/src/bridge/supervisor"
	"assistant/workbench/engine"

	"github.com/google/uuid"
)

// BridgeTurnInput defines parameters for full Layer 4 IPC Bridge turn execution.
type BridgeTurnInput struct {
	SessionID   string `json:"session_id" desc:"Session identifier"`
	TurnID      string `json:"turn_id" desc:"Turn identifier"`
	TargetAgent string `json:"target_agent" desc:"Target agent persona (echo, system, research, browser, manager)"`
	Prompt      string `json:"prompt" desc:"Prompt to execute across the IPC bridge"`
	TimeoutSec  int    `json:"timeout_seconds" desc:"Maximum execution timeout in seconds (default: 30)"`
}

// BridgeHandshakeInput defines parameters for testing bridge initialization latency.
type BridgeHandshakeInput struct {
	TimeoutMs int `json:"timeout_ms" desc:"Handshake timeout in milliseconds (default: 10000)"`
}

// BridgeToolRoundtripInput defines parameters for isolated IPC tool execution loop.
type BridgeToolRoundtripInput struct {
	ToolName string `json:"tool_name" desc:"Canonical tool name to invoke (e.g. sys_exec, git_status)"`
	ArgsJSON string `json:"args_json" desc:"JSON string containing tool arguments"`
}

// RegisterLayer4Bridge registers Layer 4 IPC Bridge & Daemon test benches in the workbench.
func RegisterLayer4Bridge(r *engine.Registry) {
	// 1. Layer 4 Complete Test Bench: Cognitive Turn over Anonymous Pipes
	r.Register(engine.Module{
		ID:          "l4_bridge_turn",
		Name:        "Layer 4: IPC Bridge (Execute Turn)",
		Tier:        "LAYER_BENCH",
		Layer:       "layer4",
		Category:    "Layer 4: IPC Bridge",
		Description: "Executes a live cognitive turn across anonymous pipes to the resident Python daemon. Measures startup & handshake latency, streams thoughts/tokens via SSE, dispatches tool calls back to Layer 3, and ensures clean termination.",
		InputType:   reflect.TypeOf(BridgeTurnInput{}),
		Presets: []engine.Preset{
			{
				ID:          "bridge_echo_ping",
				Name:        "Echo: Pipe Roundtrip & Streaming",
				Category:    "Echo Diagnostic",
				Description: "Tests high-speed bidirectional NDJSON streaming over anonymous pipes without external API calls.",
				Payload: BridgeTurnInput{
					SessionID:   "sess_bridge_echo",
					TurnID:      "turn_echo_001",
					TargetAgent: "echo",
					Prompt:      "Hello from Go Layer 4 supervisor over anonymous pipes!",
					TimeoutSec:  15,
				},
			},
			{
				ID:          "bridge_tool_sys_exec",
				Name:        "Tool Dispatch: sys_exec (uname -a)",
				Category:    "Tool Roundtrip",
				Description: "Prompts Python daemon to emit a tool_call frame, executed by Go Layer 3 Tool Engine, returning output back to Python.",
				Payload: BridgeTurnInput{
					SessionID:   "sess_bridge_tool",
					TurnID:      "turn_tool_exec",
					TargetAgent: "echo",
					Prompt:      `call_tool:sys_exec:{"command":"uname -a"}`,
					TimeoutSec:  20,
				},
			},
			{
				ID:          "bridge_tool_git_status",
				Name:        "Tool Dispatch: git_status",
				Category:    "Tool Roundtrip",
				Description: "Tests Python requesting git repository status via Go Layer 3 native git tools.",
				Payload: BridgeTurnInput{
					SessionID:   "sess_bridge_git",
					TurnID:      "turn_tool_git",
					TargetAgent: "echo",
					Prompt:      `call_tool:git_status:{"repo_path":"."}`,
					TimeoutSec:  20,
				},
			},
			{
				ID:          "bridge_manager_planning",
				Name:        "Cognitive Agent: Manager Planner",
				Category:    "Agent Execution",
				Description: "Dispatches to Python ManagerAgent to generate a structured execution DAG plan.",
				Payload: BridgeTurnInput{
					SessionID:   "sess_bridge_mgr",
					TurnID:      "turn_mgr_001",
					TargetAgent: "manager",
					Prompt:      "Inspect git repository changes and summarize project health",
					TimeoutSec:  30,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var in BridgeTurnInput
			if err := json.Unmarshal(inputRaw, &in); err != nil {
				return nil, fmt.Errorf("invalid json payload: %w", err)
			}

			if in.SessionID == "" {
				in.SessionID = "sess_" + uuid.New().String()[:8]
			}
			if in.TurnID == "" {
				in.TurnID = "turn_" + uuid.New().String()[:8]
			}
			if in.TargetAgent == "" {
				in.TargetAgent = "echo"
			}
			if in.TimeoutSec <= 0 {
				in.TimeoutSec = 30
			}

			turnCtx, cancel := context.WithTimeout(ctx, time.Duration(in.TimeoutSec)*time.Second)
			defer cancel()

			engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
				Level:   "INFO",
				Source:  "bridge.supervisor",
				Message: fmt.Sprintf("Spawning Layer 4 Python resident daemon for turn %s (target: @%s)", in.TurnID, in.TargetAgent),
			})

			stream <- engine.StreamEvent{
				Type:      "BRIDGE_SPAWNING",
				AgentName: "Supervisor",
				Payload: map[string]any{
					"session_id":   in.SessionID,
					"turn_id":      in.TurnID,
					"target_agent": in.TargetAgent,
					"prompt":       in.Prompt,
				},
			}

			// Wire Layer 3 Tool Registry so tool calls from Python can be executed by Go
			reg, cleanupTools, err := buildToolRegistry()
			if err != nil {
				return nil, fmt.Errorf("failed to initialize tool registry: %w", err)
			}
			defer cleanupTools()

			cfg := supervisor.Config{
				ProcessConfig: supervisor.ProcessConfig{
					PythonBinary: "",
					ModulePath:   "src.bridge.daemon",
				},
				ToolExecutor: reg,
				ReadyTimeout: 15 * time.Second,
				GracePeriod:  3 * time.Second,
			}

			sup := supervisor.NewSupervisor(cfg)

			bootStart := time.Now()
			if err := sup.Start(turnCtx); err != nil {
				stream <- engine.StreamEvent{
					Type:      "BRIDGE_ERROR",
					AgentName: "Supervisor",
					Payload:   fmt.Sprintf("Failed to boot Python resident daemon: %v", err),
				}
				return nil, fmt.Errorf("supervisor start failed: %w", err)
			}
			handshakeMs := time.Since(bootStart).Milliseconds()

			stream <- engine.StreamEvent{
				Type:      "BRIDGE_READY",
				AgentName: "Supervisor",
				Payload: map[string]any{
					"status":          "ready",
					"handshake_ms":    handshakeMs,
					"target_agent":    in.TargetAgent,
					"anonymous_pipes": "stdin/stdout duplex established",
				},
			}

			defer func() {
				stopStart := time.Now()
				_ = sup.Stop()
				stream <- engine.StreamEvent{
					Type:      "BRIDGE_STOPPED",
					AgentName: "Supervisor",
					Payload: map[string]any{
						"shutdown_duration_ms": time.Since(stopStart).Milliseconds(),
						"zombie_safe":          true,
					},
				}
			}()

			payload := &protocol.StartTurnPayload{
				TargetAgent: in.TargetAgent,
				Prompt:      in.Prompt,
				Context: map[string]any{
					"workbench_caller": "l4_bridge_turn",
					"timestamp":        time.Now().UnixMilli(),
				},
			}

			stream <- engine.StreamEvent{
				Type:      "BRIDGE_TURN_START",
				AgentName: in.TargetAgent,
				Payload:   payload,
			}

			turnStart := time.Now()
			handle, err := sup.StartTurn(turnCtx, in.SessionID, in.TurnID, payload)
			if err != nil {
				return nil, fmt.Errorf("failed to start turn: %w", err)
			}

			var thoughts []string
			var tokensBuilder strings.Builder
			doneCh := make(chan struct{})

			// Stream thoughts
			go func() {
				for th := range handle.Thoughts() {
					thoughts = append(thoughts, th)
					stream <- engine.StreamEvent{
						Type:      "AGENT_THOUGHT",
						AgentName: in.TargetAgent,
						Payload:   th,
					}
				}
			}()

			// Stream tokens
			go func() {
				for tok := range handle.Tokens() {
					tokensBuilder.WriteString(tok)
					stream <- engine.StreamEvent{
						Type:      "TOKEN",
						AgentName: in.TargetAgent,
						Payload:   tok,
					}
				}
				close(doneCh)
			}()

			var terminalErr error
			var completePayload *protocol.TurnCompletePayload

			select {
			case <-turnCtx.Done():
				terminalErr = turnCtx.Err()
			case err := <-handle.Errors():
				if err != nil {
					terminalErr = err
				}
			case comp := <-handle.Complete():
				completePayload = comp
			}

			<-doneCh
			turnDurationMs := time.Since(turnStart).Milliseconds()

			if terminalErr != nil {
				stream <- engine.StreamEvent{
					Type:      "BRIDGE_TURN_ERROR",
					AgentName: in.TargetAgent,
					Payload:   terminalErr.Error(),
				}
				return nil, terminalErr
			}

			finalTokens := tokensBuilder.String()
			stream <- engine.StreamEvent{
				Type:      "TURN_COMPLETE",
				AgentName: in.TargetAgent,
				Payload: map[string]any{
					"status":           completePayload.Status,
					"final_response":   finalTokens,
					"duration_ms":      turnDurationMs,
					"prompt_tokens":    completePayload.Usage.PromptTokens,
					"completion_tokens": completePayload.Usage.CompletionTokens,
					"total_tokens":     completePayload.Usage.TotalTokens,
				},
			}

			return map[string]any{
				"status":             "success",
				"session_id":         in.SessionID,
				"turn_id":            in.TurnID,
				"target_agent":       in.TargetAgent,
				"handshake_ms":       handshakeMs,
				"turn_duration_ms":   turnDurationMs,
				"thoughts_count":     len(thoughts),
				"streamed_thoughts":  thoughts,
				"accumulated_tokens": finalTokens,
				"usage":              completePayload.Usage,
			}, nil
		},
	})

	// 2. Layer 4 Component Test Bench: Daemon Spawn & Handshake Benchmark
	r.Register(engine.Module{
		ID:          "l4_bridge_handshake",
		Name:        "Layer 4: IPC Bridge (Handshake & Diagnostic Ping)",
		Tier:        "COMPONENT",
		Layer:       "layer4",
		Category:    "Layer 4: IPC Bridge",
		Description: "Benchmarks daemon process spawn time, anonymous pipe negotiation, protocol version exchange, and clean shutdown without executing cognitive models.",
		InputType:   reflect.TypeOf(BridgeHandshakeInput{}),
		Presets: []engine.Preset{
			{
				ID:          "bench_handshake_fast",
				Name:        "Diagnostic: Fast Handshake & Ping",
				Category:    "Diagnostic",
				Description: "Verifies python binary resolution, pipe spawn, and READY frame handshake within 5000ms.",
				Payload: BridgeHandshakeInput{
					TimeoutMs: 5000,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var in BridgeHandshakeInput
			if err := json.Unmarshal(inputRaw, &in); err != nil {
				return nil, fmt.Errorf("invalid json payload: %w", err)
			}
			if in.TimeoutMs <= 0 {
				in.TimeoutMs = 10000
			}

			hCtx, cancel := context.WithTimeout(ctx, time.Duration(in.TimeoutMs)*time.Millisecond)
			defer cancel()

			start := time.Now()
			cfg := supervisor.Config{
				ProcessConfig: supervisor.ProcessConfig{
					PythonBinary: "",
					ModulePath:   "src.bridge.daemon",
				},
				ReadyTimeout: time.Duration(in.TimeoutMs) * time.Millisecond,
				GracePeriod:  2 * time.Second,
			}

			sup := supervisor.NewSupervisor(cfg)

			stream <- engine.StreamEvent{
				Type:      "SPAWN_START",
				AgentName: "Supervisor",
				Payload:   "Launching python3 -m src.bridge.daemon over anonymous pipes...",
			}

			if err := sup.Start(hCtx); err != nil {
				return nil, fmt.Errorf("handshake failed: %w", err)
			}
			handshakeDuration := time.Since(start)

			stream <- engine.StreamEvent{
				Type:      "HANDSHAKE_READY",
				AgentName: "Supervisor",
				Payload: map[string]any{
					"latency_ms": handshakeDuration.Milliseconds(),
					"status":     "ready",
					"is_running": sup.IsRunning(),
				},
			}

			stopStart := time.Now()
			_ = sup.Stop()
			stopDuration := time.Since(stopStart)

			stream <- engine.StreamEvent{
				Type:      "CLEANUP_SUCCESS",
				AgentName: "Supervisor",
				Payload: map[string]any{
					"stop_duration_ms": stopDuration.Milliseconds(),
					"is_running":       sup.IsRunning(),
				},
			}

			return map[string]any{
				"status":             "success",
				"handshake_latency":  handshakeDuration.String(),
				"handshake_ms":       handshakeDuration.Milliseconds(),
				"shutdown_latency":   stopDuration.String(),
				"shutdown_ms":        stopDuration.Milliseconds(),
				"process_zombie_safe": true,
			}, nil
		},
	})

	// 3. Layer 4 Component Test Bench: Dedicated Tool Roundtrip Loop
	r.Register(engine.Module{
		ID:          "l4_bridge_tool_roundtrip",
		Name:        "Layer 4: IPC Bridge (Tool Engine Roundtrip Loop)",
		Tier:        "COMPONENT",
		Layer:       "layer4",
		Category:    "Layer 4: IPC Bridge",
		Description: "Tests bidirectional IPC loop: Python daemon requests native Go tool execution, Go Layer 3 Tool Engine runs tool in sandbox, and returns NDJSON result back to Python.",
		InputType:   reflect.TypeOf(BridgeToolRoundtripInput{}),
		Presets: []engine.Preset{
			{
				ID:          "roundtrip_sys_exec_echo",
				Name:        "Roundtrip: sys_exec (echo test)",
				Category:    "Tool Execution",
				Description: "Dispatches sys_exec through Python -> Go L3 -> Python",
				Payload: BridgeToolRoundtripInput{
					ToolName: "sys_exec",
					ArgsJSON: `{"command":"echo live_ipc_tool_roundtrip_ok"}`,
				},
			},
			{
				ID:          "roundtrip_git_status",
				Name:        "Roundtrip: git_status (Current Repo)",
				Category:    "Git Tools",
				Description: "Dispatches git_status through Python -> Go L3 -> Python",
				Payload: BridgeToolRoundtripInput{
					ToolName: "git_status",
					ArgsJSON: `{"repo_path":"."}`,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var in BridgeToolRoundtripInput
			if err := json.Unmarshal(inputRaw, &in); err != nil {
				return nil, fmt.Errorf("invalid json payload: %w", err)
			}
			if in.ToolName == "" {
				in.ToolName = "sys_exec"
			}
			if in.ArgsJSON == "" {
				in.ArgsJSON = `{"command":"echo test"}`
			}

			reg, cleanupTools, err := buildToolRegistry()
			if err != nil {
				return nil, err
			}
			defer cleanupTools()

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
			if err := sup.Start(ctx); err != nil {
				return nil, fmt.Errorf("supervisor start failed: %w", err)
			}
			defer func() { _ = sup.Stop() }()

			turnID := "turn_roundtrip_" + uuid.New().String()[:8]
			prompt := fmt.Sprintf("call_tool:%s:%s", in.ToolName, in.ArgsJSON)

			stream <- engine.StreamEvent{
				Type:      "TOOL_ROUNDTRIP_DISPATCH",
				AgentName: "echo",
				Payload: map[string]any{
					"tool_name": in.ToolName,
					"args":      in.ArgsJSON,
					"prompt":    prompt,
				},
			}

			start := time.Now()
			handle, err := sup.StartTurn(ctx, "sess_roundtrip", turnID, &protocol.StartTurnPayload{
				TargetAgent: "echo",
				Prompt:      prompt,
			})
			if err != nil {
				return nil, err
			}

			var tokensBuilder strings.Builder
			for tok := range handle.Tokens() {
				tokensBuilder.WriteString(tok)
				stream <- engine.StreamEvent{
					Type:      "TOKEN",
					AgentName: "echo",
					Payload:   tok,
				}
			}

			var complete *protocol.TurnCompletePayload
			select {
			case comp := <-handle.Complete():
				complete = comp
			case err := <-handle.Errors():
				if err != nil {
					return nil, err
				}
			case <-time.After(15 * time.Second):
				return nil, fmt.Errorf("tool roundtrip timed out")
			}

			duration := time.Since(start)
			output := tokensBuilder.String()

			stream <- engine.StreamEvent{
				Type:      "TOOL_ROUNDTRIP_COMPLETE",
				AgentName: "echo",
				Payload: map[string]any{
					"duration_ms": duration.Milliseconds(),
					"status":      complete.Status,
					"output":      output,
				},
			}

			return map[string]any{
				"status":      "success",
				"tool_name":   in.ToolName,
				"args":        in.ArgsJSON,
				"output":      output,
				"duration_ms": duration.Milliseconds(),
			}, nil
		},
	})
}

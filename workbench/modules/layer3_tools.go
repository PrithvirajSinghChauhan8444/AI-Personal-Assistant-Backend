package modules

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"time"

	"assistant/src/tools"
	"assistant/src/tools/dispatcher"
	"assistant/workbench/engine"

	_ "modernc.org/sqlite"
)

// ToolExecutionInput defines the parameters for isolated Layer 3 tool execution.
type ToolExecutionInput struct {
	ToolName string `json:"tool_name" desc:"Canonical tool name (e.g. git_status, fs_read, sys_exec)"`
	ArgsJSON string `json:"args_json" desc:"JSON string containing tool arguments"`
}

// ToolToggleInput defines parameters to toggle a tool's live enabled status.
type ToolToggleInput struct {
	ToolName string `json:"tool_name" desc:"Canonical tool name to toggle"`
	Enabled  bool   `json:"enabled" desc:"Whether the tool is enabled"`
}

func buildToolRegistry() (*tools.ToolRegistry, func(), error) {
	dataDir := filepath.Join("workspace", "workbench", "data")
	_ = os.MkdirAll(dataDir, 0755)
	artifactsDir := filepath.Join("workspace", "workbench", "artifacts")
	_ = os.MkdirAll(artifactsDir, 0755)

	dbPath := filepath.Join(dataDir, "tools_bench.db")
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to open sqlite database: %w", err)
	}

	spillover := tools.NewSpilloverManager(artifactsDir, 100*1024)
	reg := tools.NewToolRegistry(db, spillover)

	if err := dispatcher.RegisterAllTools(reg, "config"); err != nil {
		_ = db.Close()
		return nil, nil, fmt.Errorf("failed to register tools: %w", err)
	}

	cleanup := func() {
		_ = db.Close()
	}

	return reg, cleanup, nil
}

// RegisterLayer3Tools registers the Layer 3 Tool Engine manual test benches in the workbench.
func RegisterLayer3Tools(r *engine.Registry) {
	// 1. Layer 3 Complete Test Bench: Native Tool Execution
	r.Register(engine.Module{
		ID:          "l3_tool_execute",
		Name:        "Layer 3: Tool Engine (Execute Native Tool)",
		Tier:        "LAYER_BENCH",
		Layer:       "layer3",
		Category:    "Layer 3: Tool Engine",
		Description: "Executes a native tool through the isolated Layer 3 Tool Engine with sandboxing, spillover, latency tracking, and structured output.",
		InputType:   reflect.TypeOf(ToolExecutionInput{}),
		Presets: []engine.Preset{
			{
				ID:          "git_status_root",
				Name:        "Git: Status (Current Repo)",
				Category:    "Git Tools",
				Description: "Inspects git working directory status, branch, and staged files",
				Payload: ToolExecutionInput{
					ToolName: "git_status",
					ArgsJSON: `{"repo_path": "."}`,
				},
			},
			{
				ID:          "git_diff_check",
				Name:        "Git: Diff (Unstaged Changes)",
				Category:    "Git Tools",
				Description: "Inspects unstaged git modifications across workspace",
				Payload: ToolExecutionInput{
					ToolName: "git_diff",
					ArgsJSON: `{"repo_path": "."}`,
				},
			},
			{
				ID:          "fs_read_gomod",
				Name:        "Filesystem: Read go.mod",
				Category:    "Filesystem Tools",
				Description: "Reads line 1 to 20 of project go.mod",
				Payload: ToolExecutionInput{
					ToolName: "fs_read",
					ArgsJSON: `{"path": "go.mod", "start_line": 1, "end_line": 20}`,
				},
			},
			{
				ID:          "fs_list_src",
				Name:        "Filesystem: List src/ Directory",
				Category:    "Filesystem Tools",
				Description: "Lists contents of the src/ architecture root",
				Payload: ToolExecutionInput{
					ToolName: "fs_list",
					ArgsJSON: `{"path": "src", "recursive": false, "max_depth": 1}`,
				},
			},
			{
				ID:          "fs_ripgrep_search",
				Name:        "Filesystem: Ripgrep Search (ToolRegistry)",
				Category:    "Filesystem Tools",
				Description: "Fast regex search across Go codebase using fs_ripgrep",
				Payload: ToolExecutionInput{
					ToolName: "fs_ripgrep",
					ArgsJSON: `{"query": "ToolRegistry", "path": "src"}`,
				},
			},
			{
				ID:          "fs_write_scratch",
				Name:        "Filesystem: Write Scratch File",
				Category:    "Filesystem Tools",
				Description: "Writes a verified test file into workbench workspace",
				Payload: ToolExecutionInput{
					ToolName: "fs_write",
					ArgsJSON: `{"path": "workspace/workbench/data/bench_test.txt", "content": "Layer 3 Tool Bench Verification Payload"}`,
				},
			},
			{
				ID:          "sys_exec_version",
				Name:        "System: Run go version",
				Category:    "System Tools",
				Description: "Executes command line binary via sys_exec with timeout and exit code capture",
				Payload: ToolExecutionInput{
					ToolName: "sys_exec",
					ArgsJSON: `{"command": "go version"}`,
				},
			},
			{
				ID:          "sys_ps_list",
				Name:        "System: Process List (sys_ps)",
				Category:    "System Tools",
				Description: "Lists running system processes with PID, CPU, and Memory usage",
				Payload: ToolExecutionInput{
					ToolName: "sys_ps",
					ArgsJSON: `{}`,
				},
			},
			{
				ID:          "net_fetch_httpbin",
				Name:        "Network: Fetch HTTP URL",
				Category:    "Network Tools",
				Description: "Performs HTTP GET via net_fetch with header validation",
				Payload: ToolExecutionInput{
					ToolName: "net_fetch",
					ArgsJSON: `{"url": "https://example.com"}`,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var in ToolExecutionInput
			if err := json.Unmarshal(inputRaw, &in); err != nil {
				return nil, fmt.Errorf("invalid json for ToolExecutionInput: %w", err)
			}

			if in.ToolName == "" {
				return nil, fmt.Errorf("tool_name is required")
			}
			if in.ArgsJSON == "" {
				in.ArgsJSON = "{}"
			}

			reg, cleanup, err := buildToolRegistry()
			if err != nil {
				return nil, err
			}
			defer cleanup()

			tool, exists := reg.GetTool(in.ToolName)
			riskLevel := "UNKNOWN"
			if exists {
				riskLevel = string(tool.Metadata().Risk)
			}

			stream <- engine.StreamEvent{
				Index:     1,
				Timestamp: time.Now(),
				Type:      "TOOL_STARTED",
				AgentName: "Layer3Tools",
				Payload: map[string]any{
					"tool_name":  in.ToolName,
					"args":       in.ArgsJSON,
					"risk_level": riskLevel,
				},
			}

			startTime := time.Now()
			res, execErr := reg.Execute(ctx, in.ToolName, in.ArgsJSON)
			duration := time.Since(startTime)

			if execErr != nil {
				stream <- engine.StreamEvent{
					Index:     2,
					Timestamp: time.Now(),
					Type:      "TOOL_ERROR",
					AgentName: "Layer3Tools",
					Payload:   execErr.Error(),
				}
				return nil, execErr
			}

			if res != nil {
				if res.Stdout != "" {
					stream <- engine.StreamEvent{
						Index:     3,
						Timestamp: time.Now(),
						Type:      "TOOL_STDOUT",
						AgentName: in.ToolName,
						Payload:   res.Stdout,
					}
				}
				if res.Stderr != "" {
					stream <- engine.StreamEvent{
						Index:     4,
						Timestamp: time.Now(),
						Type:      "TOOL_STDERR",
						AgentName: in.ToolName,
						Payload:   res.Stderr,
					}
				}
				if res.ArtifactPath != "" {
					stream <- engine.StreamEvent{
						Index:     5,
						Timestamp: time.Now(),
						Type:      "TOOL_SPILLOVER",
						AgentName: "SpilloverManager",
						Payload:   fmt.Sprintf("Output exceeded 100KB threshold. Committed to artifact: %s", res.ArtifactPath),
					}
				}

				stream <- engine.StreamEvent{
					Index:     6,
					Timestamp: time.Now(),
					Type:      "TOOL_FINISHED",
					AgentName: "Layer3Tools",
					Payload: map[string]any{
						"exit_code":   res.ExitCode,
						"duration_ms": duration.Milliseconds(),
						"is_error":    res.IsError,
					},
				}
			}

			return map[string]any{
				"tool":        in.ToolName,
				"result":      res,
				"risk_level":  riskLevel,
				"duration_ms": duration.Milliseconds(),
				"status":      "SUCCESS",
			}, nil
		},
	})

	// 2. Layer 3 Tool Catalog & Active Discovery
	r.Register(engine.Module{
		ID:          "l3_tool_catalog",
		Name:        "Layer 3: Tool Catalog & Discovery",
		Tier:        "COMPONENT",
		Layer:       "layer3",
		Category:    "Layer 3: Tool Engine",
		Description: "Inspects all registered tools in the Layer 3 Tool Engine, their parameter schemas, prompt usage tips, and active security toggles.",
		InputType:   reflect.TypeOf(map[string]any{}),
		Presets: []engine.Preset{
			{
				ID:          "catalog_all",
				Name:        "List All Registered Tools",
				Category:    "Discovery",
				Description: "Discovers all active system, filesystem, git, network, and workspace tools",
				Payload:     map[string]any{},
			},
		},
		Execute: func(ctx context.Context, _ json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			reg, cleanup, err := buildToolRegistry()
			if err != nil {
				return nil, err
			}
			defer cleanup()

			active := reg.GetActiveTools(nil)
			stream <- engine.StreamEvent{
				Index:     1,
				Timestamp: time.Now(),
				Type:      "CATALOG_LOADED",
				AgentName: "ToolRegistry",
				Payload:   fmt.Sprintf("Discovered %d active native tools in Layer 3 Tool Engine", len(active)),
			}

			return map[string]any{
				"total_tools": len(active),
				"tools":       active,
			}, nil
		},
	})

	// 3. Layer 3 Tool Toggle (Runtime Security)
	r.Register(engine.Module{
		ID:          "l3_tool_toggle",
		Name:        "Layer 3: Tool Security Toggle",
		Tier:        "COMPONENT",
		Layer:       "layer3",
		Category:    "Layer 3: Tool Engine",
		Description: "Enables or disables tools at runtime in SQLite and verifies execution lockout behavior.",
		InputType:   reflect.TypeOf(ToolToggleInput{}),
		Presets: []engine.Preset{
			{
				ID:          "disable_sys_exec",
				Name:        "Disable sys_exec Tool",
				Category:    "Security Lockout",
				Description: "Disables dangerous command execution tool",
				Payload: ToolToggleInput{
					ToolName: "sys_exec",
					Enabled:  false,
				},
			},
			{
				ID:          "enable_sys_exec",
				Name:        "Enable sys_exec Tool",
				Category:    "Security Recovery",
				Description: "Restores command execution tool",
				Payload: ToolToggleInput{
					ToolName: "sys_exec",
					Enabled:  true,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var in ToolToggleInput
			if err := json.Unmarshal(inputRaw, &in); err != nil {
				return nil, err
			}

			reg, cleanup, err := buildToolRegistry()
			if err != nil {
				return nil, err
			}
			defer cleanup()

			if err := reg.SetToolStatus(in.ToolName, in.Enabled); err != nil {
				return nil, err
			}

			stream <- engine.StreamEvent{
				Index:     1,
				Timestamp: time.Now(),
				Type:      "TOOL_TOGGLED",
				AgentName: "ToolRegistry",
				Payload:   fmt.Sprintf("Tool %q state transitioned to enabled=%t", in.ToolName, in.Enabled),
			}

			return map[string]any{
				"tool":    in.ToolName,
				"enabled": in.Enabled,
				"status":  "TOGGLE_UPDATED",
			}, nil
		},
	})
}

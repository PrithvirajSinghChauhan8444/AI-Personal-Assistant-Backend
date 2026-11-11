package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"assistant/src/bridge/supervisor"
	"assistant/src/gateway"
	"assistant/src/gateway/adapters/cli"
	"assistant/src/orchestrator"
	"assistant/src/orchestrator/planner"
	"assistant/src/orchestrator/safety"
	"assistant/src/orchestrator/session"
	"assistant/src/tools"
	"assistant/src/tools/dispatcher"
)

type systemConfig struct {
	WorkspaceDir                string   `json:"workspace_dir"`
	ArtifactsDir                string   `json:"artifacts_dir"`
	DatabasePath                string   `json:"database_path"`
	NotesDir                    string   `json:"notes_dir"`
	AllowedAccessRoots          []string `json:"allowed_access_roots"`
	Timezone                    string   `json:"timezone"`
	LogLevel                    string   `json:"log_level"`
	MaxTurnIterations           int      `json:"max_turn_iterations"`
	ArtifactSpilloverThreshold  int64    `json:"artifact_spillover_threshold_bytes"`
}

func loadSystemConfig(path string) systemConfig {
	cfg := systemConfig{
		WorkspaceDir:       "workspace",
		ArtifactsDir:       filepath.Join("workspace", "artifacts"),
		DatabasePath:       filepath.Join("workspace", "data", "sessions.db"),
		NotesDir:           filepath.Join("workspace", "obsidian_vault"),
		AllowedAccessRoots: []string{"workspace"},
		Timezone:           "UTC",
		LogLevel:           "INFO",
		MaxTurnIterations:  10,
	}
	if data, err := os.ReadFile(path); err == nil {
		_ = json.Unmarshal(data, &cfg)
	}
	return cfg
}

func main() {
	sysCfg := loadSystemConfig(filepath.Join("config", "system.json"))

	prompt := flag.String("prompt", "", "Single prompt execution mode")
	planOnly := flag.Bool("plan-only", false, "Run only the Manager Agent planner and print the task plan DAG without dispatching workers")
	standalone := flag.Bool("standalone", false, "Run in standalone mode without Layer 4 Python bridge")
	sessionID := flag.String("session", "", "Session ID override")
	workspaceDir := flag.String("workspace", sysCfg.WorkspaceDir, "Path to agent workspace directory")
	dbPath := flag.String("db", sysCfg.DatabasePath, "Path to SQLite session database")
	artifactsDir := flag.String("artifacts", sysCfg.ArtifactsDir, "Path to artifacts directory")
	flag.Parse()

	// Ensure runtime directories exist
	_ = os.MkdirAll(*workspaceDir, 0755)
	_ = os.MkdirAll(*artifactsDir, 0755)
	_ = os.MkdirAll(filepath.Dir(*dbPath), 0755)

	ctx := context.Background()

	// Plan-only mode: Run only the Layer 2 Manager Agent
	if *planOnly {
		goal := *prompt
		if goal == "" {
			fmt.Fprintln(os.Stderr, "Error: --prompt is required when using --plan-only")
			os.Exit(1)
		}
		mgr := planner.NewManagerAgent(nil, nil, "")
		plan, err := mgr.Plan(ctx, goal, nil)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Manager planning error: %v\n", err)
			os.Exit(1)
		}
		out, _ := json.MarshalIndent(plan, "", "  ")
		fmt.Println(string(out))
		return
	}

	// Initialize Layer 2 Persistent SQLite Store
	store, err := session.NewSQLiteStore(*dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to initialize session store: %v\n", err)
		os.Exit(1)
	}
	defer store.Close()

	// Initialize Safety Gatekeeper and load user policy overrides
	gk := safety.NewGatekeeper()
	safetyConfigPath := filepath.Join("config", "safety_policies.json")
	if _, err := os.Stat(safetyConfigPath); err == nil {
		_ = gk.LoadPoliciesFromFile(safetyConfigPath)
	}

	// Initialize Layer 2 Executor (BridgeTurnExecutor to Layer 4 Python or Standalone fallback)
	var turnExecutor orchestrator.TurnExecutor
	var bridgeSup *supervisor.Supervisor

	if !*standalone {
		// Initialize Layer 3 Tool Engine & Registry
		spillThreshold := sysCfg.ArtifactSpilloverThreshold
		if spillThreshold <= 0 {
			spillThreshold = tools.DefaultSpilloverThresholdBytes
		}
		toolSpillover := tools.NewSpilloverManager(*artifactsDir, int(spillThreshold))
		toolRegistry := tools.NewToolRegistry(nil, toolSpillover)
		if err := dispatcher.RegisterAllTools(toolRegistry, "config"); err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to register some native tools: %v\n", err)
		}

		// Initialize Layer 4 IPC Bridge Supervisor
		bridgeCfg := supervisor.Config{
			ProcessConfig: supervisor.ProcessConfig{
				PythonBinary: "",
				ModulePath:   "src.bridge.daemon",
			},
			ToolExecutor: toolRegistry,
			ReadyTimeout: 15 * time.Second,
			GracePeriod:  3 * time.Second,
		}
		bridgeSup = supervisor.NewSupervisor(bridgeCfg)
		if err := bridgeSup.Start(ctx); err != nil {
			fmt.Fprintf(os.Stderr, "Fatal: failed to start Layer 4 bridge supervisor: %v\n", err)
			os.Exit(1)
		}
		defer func() {
			_ = bridgeSup.Stop()
		}()

		turnExecutor = orchestrator.NewBridgeTurnExecutor(bridgeSup)
	} else {
		turnExecutor = orchestrator.NewStandaloneExecutor()
	}

	// Initialize Layer 2 Orchestrator
	orch, err := orchestrator.New(orchestrator.Config{
		Store:        store,
		Gatekeeper:   gk,
		Executor:     turnExecutor,
		ArtifactsDir: *artifactsDir,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to initialize orchestrator: %v\n", err)
		if bridgeSup != nil {
			_ = bridgeSup.Stop()
		}
		os.Exit(1)
	}

	// Initialize Layer 1 Standard Gateway backed by Layer 2 Orchestrator
	gw, err := gateway.NewGateway(orch)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to initialize gateway: %v\n", err)
		if bridgeSup != nil {
			_ = bridgeSup.Stop()
		}
		os.Exit(1)
	}

	// Single turn execution mode (CLI flag)
	if *prompt != "" {
		rawReq := gateway.InboundTurnRequest{
			SessionID: *sessionID,
			Channel:   gateway.ClientTypeCLI,
			Prompt:    *prompt,
		}
		if err := cli.RunSingleTurn(ctx, gw, rawReq, os.Stdout); err != nil {
			fmt.Fprintf(os.Stderr, "Turn error: %v\n", err)
			if bridgeSup != nil {
				_ = bridgeSup.Stop()
			}
			os.Exit(1)
		}
		return
	}

	// Full interactive REPL mode
	adapter := cli.NewCLIAdapter(gw, os.Stdin, os.Stdout, *sessionID)
	if err := adapter.StartInteractive(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "Session ended with error: %v\n", err)
		if bridgeSup != nil {
			_ = bridgeSup.Stop()
		}
		os.Exit(1)
	}
}

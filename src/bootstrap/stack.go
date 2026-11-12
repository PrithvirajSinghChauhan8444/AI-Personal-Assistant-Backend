package bootstrap

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"assistant/src/bridge/supervisor"
	"assistant/src/gateway"
	"assistant/src/orchestrator"
	"assistant/src/orchestrator/safety"
	"assistant/src/orchestrator/session"
	"assistant/src/tools"
	"assistant/src/tools/dispatcher"
)

// Config defines the unified runtime configuration for the assistant application.
type Config struct {
	WorkspaceDir               string   `json:"workspace_dir"`
	ArtifactsDir               string   `json:"artifacts_dir"`
	DatabasePath               string   `json:"database_path"`
	NotesDir                   string   `json:"notes_dir"`
	AllowedAccessRoots         []string `json:"allowed_access_roots"`
	Timezone                   string   `json:"timezone"`
	LogLevel                   string   `json:"log_level"`
	MaxTurnIterations          int      `json:"max_turn_iterations"`
	ArtifactSpilloverThreshold int64    `json:"artifact_spillover_threshold_bytes"`
	ConfigDir                  string   `json:"config_dir"`
	Standalone                 bool     `json:"standalone"`
	ReadyTimeout               time.Duration
	GracePeriod                time.Duration
}

// Stack encapsulates all initialized layers of the production assistant backend.
type Stack struct {
	Config       Config
	Store        session.Store
	Gatekeeper   *safety.Gatekeeper
	ToolRegistry *tools.ToolRegistry
	Supervisor   *supervisor.Supervisor
	TurnExecutor orchestrator.TurnExecutor
	Orchestrator *orchestrator.Orchestrator
	Gateway      *gateway.Gateway
}

// DefaultConfig returns production default configurations.
func DefaultConfig() Config {
	return Config{
		WorkspaceDir:       "workspace",
		ArtifactsDir:       filepath.Join("workspace", "artifacts"),
		DatabasePath:       filepath.Join("workspace", "data", "sessions.db"),
		NotesDir:           filepath.Join("workspace", "obsidian_vault"),
		AllowedAccessRoots: []string{"workspace"},
		Timezone:           "UTC",
		LogLevel:           "INFO",
		MaxTurnIterations:  10,
		ConfigDir:          "config",
		ReadyTimeout:       15 * time.Second,
		GracePeriod:        3 * time.Second,
	}
}

// LoadConfig reads the system.json configuration file or falls back to defaults.
func LoadConfig(path string) Config {
	cfg := DefaultConfig()
	if data, err := os.ReadFile(path); err == nil {
		_ = json.Unmarshal(data, &cfg)
	}
	return cfg
}

// BuildStack initializes the full end-to-end production architecture:
// Layer 1 (Gateway) -> Layer 2 (Orchestrator + SQLite Store + Gatekeeper) ->
// Layer 3 (Tool Engine + Native Registry) -> Layer 4 (IPC Bridge Supervisor) -> Layer 6 (Cognitive Agents).
func BuildStack(ctx context.Context, cfg Config) (*Stack, func(), error) {
	if cfg.ConfigDir == "" {
		cfg.ConfigDir = "config"
	}
	if cfg.ReadyTimeout == 0 {
		cfg.ReadyTimeout = 15 * time.Second
	}
	if cfg.GracePeriod == 0 {
		cfg.GracePeriod = 3 * time.Second
	}

	// 1. Ensure runtime directories exist
	_ = os.MkdirAll(cfg.WorkspaceDir, 0755)
	_ = os.MkdirAll(cfg.ArtifactsDir, 0755)
	_ = os.MkdirAll(filepath.Dir(cfg.DatabasePath), 0755)

	// 2. Initialize Layer 2 Persistent SQLite Store
	store, err := session.NewSQLiteStore(cfg.DatabasePath)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to initialize session store at %s: %w", cfg.DatabasePath, err)
	}

	// 3. Initialize Layer 2 Safety Gatekeeper
	gk := safety.NewGatekeeper()
	safetyConfigPath := filepath.Join(cfg.ConfigDir, "safety_policies.json")
	if _, err := os.Stat(safetyConfigPath); err == nil {
		_ = gk.LoadPoliciesFromFile(safetyConfigPath)
	}

	// 4. Initialize Tool Engine (Layer 3) and IPC Bridge Supervisor (Layer 4)
	var turnExecutor orchestrator.TurnExecutor
	var bridgeSup *supervisor.Supervisor
	var toolRegistry *tools.ToolRegistry

	if !cfg.Standalone {
		spillThreshold := cfg.ArtifactSpilloverThreshold
		if spillThreshold <= 0 {
			spillThreshold = tools.DefaultSpilloverThresholdBytes
		}
		toolSpillover := tools.NewSpilloverManager(cfg.ArtifactsDir, int(spillThreshold))
		toolRegistry = tools.NewToolRegistry(store.DB(), toolSpillover)

		if err := dispatcher.RegisterAllTools(toolRegistry, cfg.ConfigDir); err != nil {
			// Non-fatal warning logged to stderr
			_, _ = fmt.Fprintf(os.Stderr, "Warning: failed to register some native tools: %v\n", err)
		}

		// Load user-defined tool toggles from config/tools.json if present
		toolsConfigPath := filepath.Join(cfg.ConfigDir, "tools.json")
		if err := toolRegistry.LoadConfigFile(toolsConfigPath); err != nil {
			_, _ = fmt.Fprintf(os.Stderr, "Warning: failed to load %s: %v\n", toolsConfigPath, err)
		}

		bridgeCfg := supervisor.Config{
			ProcessConfig: supervisor.ProcessConfig{
				PythonBinary: "",
				ModulePath:   "src.bridge.daemon",
			},
			ToolExecutor: toolRegistry,
			ReadyTimeout: cfg.ReadyTimeout,
			GracePeriod:  cfg.GracePeriod,
		}

		bridgeSup = supervisor.NewSupervisor(bridgeCfg)
		if err := bridgeSup.Start(ctx); err != nil {
			store.Close()
			return nil, nil, fmt.Errorf("failed to start Layer 4 Python resident daemon: %w", err)
		}

		turnExecutor = orchestrator.NewBridgeTurnExecutor(bridgeSup)
	} else {
		turnExecutor = orchestrator.NewStandaloneExecutor()
	}

	// 5. Initialize Layer 2 Orchestrator
	orch, err := orchestrator.New(orchestrator.Config{
		Store:        store,
		Gatekeeper:   gk,
		Executor:     turnExecutor,
		ArtifactsDir: cfg.ArtifactsDir,
	})
	if err != nil {
		if bridgeSup != nil {
			_ = bridgeSup.Stop()
		}
		store.Close()
		return nil, nil, fmt.Errorf("failed to initialize orchestrator: %w", err)
	}

	// 6. Initialize Layer 1 Gateway backed by Orchestrator
	gw, err := gateway.NewGateway(orch)
	if err != nil {
		if bridgeSup != nil {
			_ = bridgeSup.Stop()
		}
		store.Close()
		return nil, nil, fmt.Errorf("failed to initialize gateway: %w", err)
	}

	stack := &Stack{
		Config:       cfg,
		Store:        store,
		Gatekeeper:   gk,
		ToolRegistry: toolRegistry,
		Supervisor:   bridgeSup,
		TurnExecutor: turnExecutor,
		Orchestrator: orch,
		Gateway:      gw,
	}

	cleanup := func() {
		if bridgeSup != nil {
			_ = bridgeSup.Stop()
		}
		store.Close()
	}

	return stack, cleanup, nil
}

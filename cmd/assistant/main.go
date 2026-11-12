package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"assistant/src/bootstrap"
	"assistant/src/gateway"
	"assistant/src/gateway/adapters/cli"
	"assistant/src/orchestrator/planner"
)

func main() {
	sysCfg := bootstrap.LoadConfig(filepath.Join("config", "system.json"))

	prompt := flag.String("prompt", "", "Single prompt execution mode")
	planOnly := flag.Bool("plan-only", false, "Run only the Manager Agent planner and print the task plan DAG without dispatching workers")
	standalone := flag.Bool("standalone", false, "Run in standalone mode without Layer 4 Python bridge")
	sessionID := flag.String("session", "", "Session ID override")
	workspaceDir := flag.String("workspace", sysCfg.WorkspaceDir, "Path to agent workspace directory")
	dbPath := flag.String("db", sysCfg.DatabasePath, "Path to SQLite session database")
	artifactsDir := flag.String("artifacts", sysCfg.ArtifactsDir, "Path to artifacts directory")
	flag.Parse()

	sysCfg.WorkspaceDir = *workspaceDir
	sysCfg.DatabasePath = *dbPath
	sysCfg.ArtifactsDir = *artifactsDir
	sysCfg.Standalone = *standalone

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

	// Build the unified end-to-end production stack (L1 -> L2 -> L3 -> L4 -> L6)
	stack, cleanup, err := bootstrap.BuildStack(ctx, sysCfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to initialize system stack: %v\n", err)
		os.Exit(1)
	}
	defer cleanup()

	// Single turn execution mode (CLI flag)
	if *prompt != "" {
		rawReq := gateway.InboundTurnRequest{
			SessionID: *sessionID,
			Channel:   gateway.ClientTypeCLI,
			Prompt:    *prompt,
		}
		if err := cli.RunSingleTurn(ctx, stack.Gateway, rawReq, os.Stdout); err != nil {
			fmt.Fprintf(os.Stderr, "Turn error: %v\n", err)
			os.Exit(1)
		}
		return
	}

	// Full interactive REPL mode
	adapter := cli.NewCLIAdapter(stack.Gateway, os.Stdin, os.Stdout, *sessionID)
	if err := adapter.StartInteractive(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "Session ended with error: %v\n", err)
		os.Exit(1)
	}
}

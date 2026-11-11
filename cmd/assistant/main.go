package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"assistant/src/gateway"
	"assistant/src/gateway/adapters/cli"
	"assistant/src/orchestrator"
	"assistant/src/orchestrator/planner"
	"assistant/src/orchestrator/safety"
	"assistant/src/orchestrator/session"
)

func main() {
	prompt := flag.String("prompt", "", "Single prompt execution mode")
	planOnly := flag.Bool("plan-only", false, "Run only the Manager Agent planner and print the task plan DAG without dispatching workers")
	sessionID := flag.String("session", "", "Session ID override")
	dbPath := flag.String("db", filepath.Join("workspace", "data", "sessions.db"), "Path to SQLite session database")
	artifactsDir := flag.String("artifacts", filepath.Join("workspace", "artifacts"), "Path to artifacts directory")
	flag.Parse()

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

	// Initialize Layer 2 Orchestrator
	orch, err := orchestrator.New(orchestrator.Config{
		Store:        store,
		Gatekeeper:   gk,
		ArtifactsDir: *artifactsDir,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to initialize orchestrator: %v\n", err)
		os.Exit(1)
	}

	// Initialize Layer 1 Standard Gateway backed by Layer 2 Orchestrator
	gw, err := gateway.NewGateway(orch)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to initialize gateway: %v\n", err)
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
			os.Exit(1)
		}
		return
	}

	// Full interactive REPL mode
	adapter := cli.NewCLIAdapter(gw, os.Stdin, os.Stdout, *sessionID)
	if err := adapter.StartInteractive(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "Session ended with error: %v\n", err)
		os.Exit(1)
	}
}

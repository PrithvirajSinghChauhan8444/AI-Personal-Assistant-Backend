package main

import (
	"context"
	"database/sql"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"assistant/src/tools"
	"assistant/src/tools/dispatcher"

	_ "modernc.org/sqlite"
)

func main() {
	toolName := flag.String("tool", "", "Tool name to execute (e.g. sys_exec, fs_read, net_fetch)")
	argsJSON := flag.String("args", "{}", "JSON arguments string for the tool")
	listTools := flag.Bool("list", false, "List all registered tools with metadata and enabled status")
	toggle := flag.String("toggle", "", "Toggle tool enabled state, format: <tool_name>=true|false")
	configDir := flag.String("config-dir", "config", "Path to config directory")
	dbPath := flag.String("db", "workspace/data/sessions.db", "Path to SQLite database for tool states and audit logging")
	artifactsDir := flag.String("artifacts-dir", "workspace/artifacts", "Directory for large payload spillovers")
	flag.Parse()

	_ = os.MkdirAll(filepath.Dir(*dbPath), 0755)
	db, err := sql.Open("sqlite", *dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Warning: failed to open SQLite db (%v). Running in-memory.\n", err)
		db = nil
	}
	if db != nil {
		defer db.Close()
	}

	spillover := tools.NewSpilloverManager(*artifactsDir, 100*1024)
	registry := tools.NewToolRegistry(db, spillover)

	if err := dispatcher.RegisterAllTools(registry, *configDir); err != nil {
		fmt.Fprintf(os.Stderr, "Error registering tools: %v\n", err)
		os.Exit(1)
	}

	if *toggle != "" {
		handleToggle(registry, *toggle)
		return
	}

	if *listTools {
		handleList(registry)
		return
	}

	if *toolName == "" {
		fmt.Println("Usage: go run ./cmd/bench/tools -tool <name> -args '<json>'")
		fmt.Println("       go run ./cmd/bench/tools -list")
		fmt.Println("       go run ./cmd/bench/tools -toggle <name>=true|false")
		os.Exit(1)
	}

	handleExecute(registry, *toolName, *argsJSON)
}

func handleList(registry *tools.ToolRegistry) {
	active := registry.GetActiveTools(nil)
	fmt.Printf("\n=== Registered Tools (%d Active) ===\n", len(active))
	fmt.Printf("%-18s %-12s %-8s %-16s %s\n", "NAME", "CATEGORY", "RISK", "CAPABILITY", "DESCRIPTION")
	fmt.Println(strings.Repeat("-", 80))
	for _, m := range active {
		status := "ENABLED"
		if !registry.IsToolEnabled(m.Name) {
			status = "DISABLED"
		}
		fmt.Printf("%-18s %-12s %-8s %-16s [%s] %s\n",
			m.Name, m.Category, m.Risk, m.RequiredCapability, status, truncate(m.Description, 50))
	}
	fmt.Println()
}

func handleToggle(registry *tools.ToolRegistry, toggleExpr string) {
	parts := strings.Split(toggleExpr, "=")
	if len(parts) != 2 {
		fmt.Fprintf(os.Stderr, "Invalid toggle syntax. Expected: <tool_name>=true|false\n")
		os.Exit(1)
	}

	name := strings.TrimSpace(parts[0])
	val := strings.ToLower(strings.TrimSpace(parts[1]))
	enabled := val == "true" || val == "1" || val == "yes"

	if err := registry.SetToolStatus(name, enabled); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to toggle %s: %v\n", name, err)
		os.Exit(1)
	}

	state := "ENABLED"
	if !enabled {
		state = "DISABLED"
	}
	fmt.Printf("✓ Tool %q is now %s\n", name, state)
}

func handleExecute(registry *tools.ToolRegistry, toolName, argsJSON string) {
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	fmt.Printf(">>> Executing Tool: %s\n", toolName)
	fmt.Printf(">>> Arguments: %s\n", argsJSON)
	fmt.Println(strings.Repeat("=", 60))

	result, err := registry.Execute(ctx, toolName, argsJSON)
	if err != nil {
		fmt.Printf("Execution returned error: %v\n", err)
	}

	fmt.Printf("Exit Code:     %d\n", result.ExitCode)
	fmt.Printf("Duration:      %d ms\n", result.DurationMs)
	fmt.Printf("Is Error:      %t\n", result.IsError)
	if result.ArtifactPath != "" {
		fmt.Printf("Artifact Spill: %s\n", result.ArtifactPath)
	}
	fmt.Println(strings.Repeat("-", 60))

	if result.Stdout != "" {
		fmt.Printf("[STDOUT]\n%s\n", result.Stdout)
	}
	if result.Stderr != "" {
		fmt.Printf("[STDERR]\n%s\n", result.Stderr)
	}
	fmt.Println(strings.Repeat("=", 60))
}

func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max-3] + "..."
}

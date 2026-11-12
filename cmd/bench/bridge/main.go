package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"assistant/src/bridge/protocol"
	"assistant/src/bridge/supervisor"
	"assistant/src/tools"
	"assistant/src/tools/dispatcher"

	_ "modernc.org/sqlite"
)

func main() {
	pythonBin := flag.String("python", "", "Path to Python executable (defaults to .venv or PATH)")
	targetAgent := flag.String("agent", "system", "Target agent persona (system, research, browser, productivity, manager)")
	prompt := flag.String("prompt", "echo 'Hello from Layer 4 Bridge'", "Prompt to send across the bridge")
	timeoutSec := flag.Int("timeout", 30, "Turn timeout in seconds")
	flag.Parse()

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	// Initialize tool registry for Layer 3 tool execution
	registry := tools.NewToolRegistry(nil, nil)
	_ = dispatcher.RegisterAllTools(registry, "config")

	cfg := supervisor.Config{
		ProcessConfig: supervisor.ProcessConfig{
			PythonBinary: *pythonBin,
			ModulePath:   "src.bridge.daemon",
		},
		ToolExecutor: registry,
		ReadyTimeout: 15 * time.Second,
		GracePeriod:  3 * time.Second,
	}

	sup := supervisor.NewSupervisor(cfg)

	fmt.Println("=== Layer 4 Stdio Bridge Bench ===")
	fmt.Printf("Starting Python resident daemon via Go supervisor...\n")

	startCtx, startCancel := context.WithTimeout(ctx, 15*time.Second)
	defer startCancel()

	if err := sup.Start(startCtx); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to start supervisor: %v\n", err)
		os.Exit(1)
	}
	defer func() {
		fmt.Println("\nStopping supervisor (zero-zombie shutdown)...")
		_ = sup.Stop()
	}()

	fmt.Println("✓ Handshake ready received! Python daemon is active.")
	fmt.Printf("Dispatching turn: agent=%s, prompt=%q\n", *targetAgent, *prompt)

	turnCtx, turnCancel := context.WithTimeout(ctx, time.Duration(*timeoutSec)*time.Second)
	defer turnCancel()

	payload := &protocol.StartTurnPayload{
		TargetAgent: *targetAgent,
		Prompt:      *prompt,
	}

	sessionID := "bench_session"
	turnID := fmt.Sprintf("turn_%d", time.Now().Unix())

	handle, err := sup.StartTurn(turnCtx, sessionID, turnID, payload)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to start turn: %v\n", err)
		os.Exit(1)
	}

	// Consume streams
	go func() {
		for thought := range handle.Thoughts() {
			fmt.Printf("\033[90m[Thought]: %s\033[0m\n", thought)
		}
	}()

	go func() {
		for token := range handle.Tokens() {
			fmt.Print(token)
		}
	}()

	select {
	case err := <-handle.Errors():
		if err != nil {
			fmt.Fprintf(os.Stderr, "\nTurn error: %v\n", err)
			os.Exit(1)
		}
	case complete := <-handle.Complete():
		if complete != nil {
			fmt.Printf("\n✓ Turn complete! Status=%s, Tokens: in=%d, out=%d, total=%d\n",
				complete.Status,
				complete.Usage.PromptTokens,
				complete.Usage.CompletionTokens,
				complete.Usage.TotalTokens,
			)
		}
	case <-turnCtx.Done():
		fmt.Fprintf(os.Stderr, "\nTurn timed out or interrupted: %v\n", turnCtx.Err())
		os.Exit(1)
	}
}

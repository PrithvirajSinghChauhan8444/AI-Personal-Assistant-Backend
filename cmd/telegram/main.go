package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"assistant/src/bootstrap"
	"assistant/src/gateway"
	"assistant/src/gateway/adapters/telegram"
	"assistant/src/orchestrator/manifest"
)

func main() {
	sysCfg := bootstrap.LoadConfig(filepath.Join("config", "system.json"))

	workspaceDir := flag.String("workspace", sysCfg.WorkspaceDir, "Path to agent workspace directory")
	dbPath := flag.String("db", sysCfg.DatabasePath, "Path to SQLite session database")
	artifactsDir := flag.String("artifacts", sysCfg.ArtifactsDir, "Path to artifacts directory")
	standalone := flag.Bool("standalone", false, "Run in standalone mode without Layer 4 Python bridge")
	watchMail := flag.Bool("watch-mail", true, "Enable proactive background Gmail watcher daemon")
	liveLogs := flag.Bool("live-logs", false, "Stream live operational logs directly to the server terminal")
	flag.Parse()

	sysCfg.WorkspaceDir = *workspaceDir
	sysCfg.DatabasePath = *dbPath
	sysCfg.ArtifactsDir = *artifactsDir
	sysCfg.Standalone = *standalone
	sysCfg.EnableMailWatcher = *watchMail

	ctx := context.Background()

	// Ensure agents registry is synchronized
	_ = manifest.SyncControlRegistry(filepath.Join("config", "agents.json"), "src/agents")

	// Build unified production stack
	stack, cleanup, err := bootstrap.BuildStack(ctx, sysCfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to initialize system stack: %v\n", err)
		os.Exit(1)
	}
	defer cleanup()

	// Always persist chronological session event logs to disk
	sessionLogsDir := filepath.Join("workspace", "logs", "sessions")
	sessionFileLogger, err := gateway.NewSessionFileLogger(sessionLogsDir)
	if err == nil {
		_ = stack.Gateway.RegisterObserver("session-file-logger", sessionFileLogger)
		defer sessionFileLogger.Close()
	}

	// Live terminal streaming logs if requested via flag
	if *liveLogs {
		termLogger := gateway.NewTerminalLogger(os.Stdout)
		_ = stack.Gateway.RegisterObserver("terminal-live-logger", termLogger)
		fmt.Println("📡 Live server terminal logging enabled.")
	}

	tgCfg := telegram.LoadConfigFromEnv()
	if tgCfg.Token == "" {
		fmt.Fprintln(os.Stderr, "❌ Error: TELEGRAM_BOT_TOKEN is not configured in your environment or .env file.")
		fmt.Fprintln(os.Stderr, "\n📋 How to configure Telegram Remote Access:")
		fmt.Fprintln(os.Stderr, "  1. Open Telegram and search for @BotFather to create a bot and get a token.")
		fmt.Fprintln(os.Stderr, "  2. Find your numeric Telegram User ID using @userinfobot.")
		fmt.Fprintln(os.Stderr, "  3. Add them to your .env file:")
		fmt.Fprintln(os.Stderr, "       TELEGRAM_BOT_TOKEN=\"your_token_here\"")
		fmt.Fprintln(os.Stderr, "       TELEGRAM_ALLOWED_USER_IDS=\"your_numeric_user_id\"")
		fmt.Fprintln(os.Stderr)
		os.Exit(1)
	}

	tgCfg.Client = telegram.NewHTTPBotClient(tgCfg.Token, nil)
	tgCfg.Gateway = stack.Gateway

	botService, err := telegram.NewBotService(tgCfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to initialize Telegram bot service: %v\n", err)
		os.Exit(1)
	}

	sigCtx, stop := signal.NotifyContext(ctx, os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := botService.Start(sigCtx); err != nil {
		fmt.Fprintf(os.Stderr, "Fatal: failed to start Telegram bot service: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("🚀 Telegram Remote Gateway is running and listening for messages.")
	fmt.Printf("🔒 Security Filter: %d authorized User ID(s) configured.\n", len(tgCfg.AllowedUserIDs))
	fmt.Println("Press Ctrl+C to terminate.")

	<-sigCtx.Done()
	fmt.Println("\n👋 Stopping Telegram Gateway gracefully...")
	botService.Stop()
}

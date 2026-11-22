package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	"assistant/src/bootstrap"
	"assistant/src/bridge/supervisor"
	"assistant/src/gateway"
	"assistant/src/adapters/cli"
	"assistant/src/adapters/telegram"
	"assistant/src/adapters/tui"
	"assistant/src/gateway/watchers/gmail"
	"assistant/src/orchestrator/manifest"
	"assistant/src/orchestrator/planner"
	"github.com/google/uuid"
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
	watchMail := flag.Bool("watch-mail", true, "Enable proactive background Gmail watcher daemon")
	runTelegram := flag.Bool("telegram", false, "Run Telegram Bot ingress gateway daemon")
	runTUI := flag.Bool("tui", false, "Run full interactive dual-pane TUI adapter")
	liveLogs := flag.Bool("live-logs", false, "Stream live operational logs directly to the server terminal")
	flag.Parse()

	sysCfg.WorkspaceDir = *workspaceDir
	sysCfg.DatabasePath = *dbPath
	sysCfg.ArtifactsDir = *artifactsDir
	sysCfg.Standalone = *standalone
	if *prompt != "" {
		sysCfg.EnableMailWatcher = false
	} else {
		sysCfg.EnableMailWatcher = *watchMail
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigCh
		cancel()
	}()

	// Ensure agents registry is synchronized and manager entry is present
	_ = manifest.SyncControlRegistry(filepath.Join("config", "agents.json"), "src/agents")

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

	// Ensure active session is set consistently across Gateway and background watchers
	activeSession := *sessionID
	if activeSession == "" {
		activeSession = uuid.NewString()
	}
	stack.Gateway.SetActiveSession(activeSession)
	if stack.MailWatcher != nil {
		stack.MailWatcher.SetSessionID(activeSession)
	}

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

	// Single turn execution mode (CLI flag)
	if *prompt != "" {
		rawReq := gateway.InboundTurnRequest{
			SessionID: activeSession,
			Channel:   gateway.ClientTypeCLI,
			Prompt:    *prompt,
		}
		if err := cli.RunSingleTurn(ctx, stack.Gateway, rawReq, os.Stdout); err != nil {
			fmt.Fprintf(os.Stderr, "Turn error: %v\n", err)
			os.Exit(1)
		}
		return
	}

	// Telegram Bot ingress gateway daemon mode
	if *runTelegram {
		runTelegramGateway(ctx, stack.Gateway)
		return
	}

	// Interactive dual-pane TUI adapter mode
	if *runTUI {
		adapter := tui.NewTUIAdapter(stack.Gateway, os.Stdin, os.Stdout, activeSession)
		adapter.SetDaemonProvider(&systemDaemonProvider{
			mailWatcher: stack.MailWatcher,
			supervisor:  stack.Supervisor,
			gw:          stack.Gateway,
		})
		if err := adapter.StartInteractive(ctx); err != nil && !errors.Is(err, context.Canceled) {
			fmt.Fprintf(os.Stderr, "TUI session ended with error: %v\n", err)
			cancel()
			cleanup()
			os.Exit(1)
		}
		cancel()
		cleanup()
		os.Exit(0)
	}

	// Full interactive REPL mode
	adapter := cli.NewCLIAdapter(stack.Gateway, os.Stdin, os.Stdout, activeSession)
	adapter.SetDaemonProvider(&systemDaemonProvider{
		mailWatcher: stack.MailWatcher,
		supervisor:  stack.Supervisor,
		gw:          stack.Gateway,
	})
	if err := adapter.StartInteractive(ctx); err != nil && !errors.Is(err, context.Canceled) {
		fmt.Fprintf(os.Stderr, "Session ended with error: %v\n", err)
		cancel()
		cleanup()
		os.Exit(1)
	}
	cancel()
	cleanup()
	os.Exit(0)
}

// systemDaemonProvider manages stack daemon inspection and lifecycle.
type systemDaemonProvider struct {
	mailWatcher *gmail.WatcherManager
	supervisor  *supervisor.Supervisor
	gw          *gateway.Gateway
}

func (p *systemDaemonProvider) ListDaemons() []cli.DaemonStatus {
	var list []cli.DaemonStatus

	// 1. Gmail Watcher
	if p.mailWatcher == nil {
		list = append(list, cli.DaemonStatus{
			Name:   "gmail-watcher",
			State:  "DISABLED",
			Detail: "disabled via config/flag",
			Active: false,
		})
	} else if p.mailWatcher.Running() {
		statuses := p.mailWatcher.Status()
		activeCount := 0
		var acctDetails []string
		for acc, st := range statuses {
			if st == gmail.StatusRunning {
				activeCount++
			}
			acctDetails = append(acctDetails, fmt.Sprintf("%s:%s", acc, st))
		}
		detail := fmt.Sprintf("%d account(s) active [%s]", activeCount, strings.Join(acctDetails, ", "))
		list = append(list, cli.DaemonStatus{
			Name:   "gmail-watcher",
			State:  "RUNNING",
			Detail: detail,
			Active: true,
		})
	} else {
		list = append(list, cli.DaemonStatus{
			Name:   "gmail-watcher",
			State:  "STOPPED",
			Detail: "mail supervisor stopped",
			Active: false,
		})
	}

	// 2. Python Bridge Daemon (Layer 4)
	if p.supervisor == nil {
		list = append(list, cli.DaemonStatus{
			Name:   "py-bridge-pipe",
			State:  "STANDALONE",
			Detail: "standalone mode (no python bridge)",
			Active: false,
		})
	} else if p.supervisor.IsRunning() {
		list = append(list, cli.DaemonStatus{
			Name:   "py-bridge-pipe",
			State:  "RUNNING",
			Detail: "kernel anonymous stdio pipes (fd 3/4)",
			Active: true,
		})
	} else {
		list = append(list, cli.DaemonStatus{
			Name:   "py-bridge-pipe",
			State:  "STOPPED",
			Detail: "resident bridge process stopped",
			Active: false,
		})
	}

	// 3. Session Governor (Layer 2)
	list = append(list, cli.DaemonStatus{
		Name:   "session-governor",
		State:  "SYNCED",
		Detail: "SQLite WAL session store & timeline",
		Active: true,
	})

	// 4. Priority Turn Queue (Layer 1)
	list = append(list, cli.DaemonStatus{
		Name:   "priority-queue",
		State:  "ACTIVE",
		Detail: "interactive & autonomous turn queue",
		Active: true,
	})

	return list
}

func (p *systemDaemonProvider) RestartDaemon(ctx context.Context, name string) error {
	switch strings.ToLower(strings.TrimSpace(name)) {
	case "gmail-watcher", "gmail":
		if p.mailWatcher == nil {
			return errors.New("gmail-watcher is not enabled in this stack")
		}
		_ = p.mailWatcher.Stop()
		return p.mailWatcher.Start(ctx)

	case "py-bridge-pipe", "bridge", "python":
		if p.supervisor == nil {
			return errors.New("python bridge is not running (standalone mode)")
		}
		_ = p.supervisor.Stop()
		return p.supervisor.Start(ctx)

	default:
		return fmt.Errorf("daemon %q does not support restart", name)
	}
}

func (p *systemDaemonProvider) StopDaemon(ctx context.Context, name string) error {
	switch strings.ToLower(strings.TrimSpace(name)) {
	case "gmail-watcher", "gmail":
		if p.mailWatcher == nil {
			return errors.New("gmail-watcher is not enabled")
		}
		return p.mailWatcher.Stop()

	case "py-bridge-pipe", "bridge", "python":
		if p.supervisor == nil {
			return errors.New("python bridge is not running")
		}
		return p.supervisor.Stop()

	default:
		return fmt.Errorf("daemon %q does not support stop", name)
	}
}

func (p *systemDaemonProvider) StartDaemon(ctx context.Context, name string) error {
	switch strings.ToLower(strings.TrimSpace(name)) {
	case "gmail-watcher", "gmail":
		if p.mailWatcher == nil {
			return errors.New("gmail-watcher is not configured")
		}
		return p.mailWatcher.Start(ctx)

	case "py-bridge-pipe", "bridge", "python":
		if p.supervisor == nil {
			return errors.New("python bridge is not running")
		}
		return p.supervisor.Start(ctx)

	default:
		return fmt.Errorf("daemon %q does not support start", name)
	}
}

func runTelegramGateway(ctx context.Context, gw *gateway.Gateway) {
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
	tgCfg.Gateway = gw

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

	fmt.Println("🚀 Telegram Bot Service is running and listening for messages.")
	fmt.Printf("🔒 Security Filter: %d authorized User ID(s) configured.\n", len(tgCfg.AllowedUserIDs))
	fmt.Println("Press Ctrl+C to terminate.")

	<-sigCtx.Done()
	fmt.Println("\n👋 Stopping Telegram Gateway gracefully...")
	botService.Stop()
}

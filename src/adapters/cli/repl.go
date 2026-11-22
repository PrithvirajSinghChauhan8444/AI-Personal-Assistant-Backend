package cli

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"runtime"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"assistant/src/gateway"
	"github.com/google/uuid"
)

// TerminalREPL coordinates clean interactive client sessions over standard terminal I/O.
type TerminalREPL struct {
	gw             *gateway.Gateway
	sessionID      string
	reader         *bufio.Reader
	out            io.Writer
	renderMu       sync.Mutex
	daemonProvider DaemonProvider
	activeAgent    string
}

// NewTerminalREPL creates an initialized REPL instance with an active session ID.
func NewTerminalREPL(gw *gateway.Gateway, in io.Reader, out io.Writer, sessionID string) *TerminalREPL {
	if sessionID == "" {
		sessionID = uuid.NewString()
	}
	return &TerminalREPL{
		gw:        gw,
		sessionID: sessionID,
		reader:    bufio.NewReader(in),
		out:       out,
	}
}

// SetDaemonProvider binds the background daemon supervisor provider to the REPL.
func (r *TerminalREPL) SetDaemonProvider(dp DaemonProvider) {
	r.daemonProvider = dp
}

// Run starts the interactive prompt loop and processes turns until exit.
func (r *TerminalREPL) Run(ctx context.Context) error {
	fmt.Fprint(r.out, RenderBanner(r.sessionID))

	// Register autonomous consumer to stream background watcher events into terminal cleanly
	if r.gw != nil {
		r.gw.RegisterAutonomousConsumer(r.sessionID, func(req gateway.InboundTurnRequest, eventCh <-chan gateway.OutboundEvent) {
			r.renderAutonomousTurn(req, eventCh)
		})
		defer r.gw.UnregisterAutonomousConsumer(r.sessionID)
	}

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		promptText, err := r.readPrompt()
		if err != nil {
			if err == io.EOF {
				fmt.Fprintln(r.out, "\nGoodbye.")
				return nil
			}
			return err
		}

		if promptText == "" {
			continue
		}

		handled, shouldExit := r.handleSlashCommand(ctx, promptText)
		if shouldExit {
			return nil
		}
		if handled {
			continue
		}

		r.executeInteractiveTurn(ctx, promptText)
	}
}

func (r *TerminalREPL) readPrompt() (string, error) {
	if r.activeAgent != "" && r.activeAgent != "auto" {
		fmt.Fprintf(r.out, "%s %s ", BrandStyle.Render("assistant"), AgentBadge(r.activeAgent))
	} else {
		fmt.Fprint(r.out, BrandStyle.Render("assistant > "))
	}
	line, err := r.reader.ReadString('\n')
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(line), nil
}

func (r *TerminalREPL) handleSlashCommand(ctx context.Context, input string) (handled bool, shouldExit bool) {
	trimmed := strings.TrimSpace(input)
	lower := strings.ToLower(trimmed)

	switch {
	case lower == "/exit" || lower == "/quit":
		fmt.Fprintln(r.out, "\nGoodbye.")
		return true, true

	case lower == "/help":
		fmt.Fprint(r.out, RenderHelp())
		return true, false

	case lower == "/clear":
		fmt.Fprint(r.out, "\033[H\033[2J")
		return true, false

	case lower == "/session":
		fmt.Fprintf(r.out, "Active Session ID: %s\n", r.sessionID)
		return true, false

	case lower == "/status":
		r.handleStatusCommand()
		return true, false

	case lower == "/checkpoint":
		fmt.Fprintf(r.out, "%s %s\n", SuccessStyle.Render("✔"), DimStyle.Render("Session snapshot saved for session: "+r.sessionID))
		return true, false

	case lower == "/daemons" || lower == "/daemon" || lower == "/daemon list" || lower == "/daemon status":
		r.handleDaemonListCommand()
		return true, false

	case strings.HasPrefix(lower, "/daemon restart "):
		target := strings.TrimSpace(trimmed[len("/daemon restart "):])
		r.handleDaemonRestartCommand(ctx, target)
		return true, false

	case strings.HasPrefix(lower, "/daemon stop "):
		target := strings.TrimSpace(trimmed[len("/daemon stop "):])
		r.handleDaemonStopCommand(ctx, target)
		return true, false

	case strings.HasPrefix(lower, "/daemon start "):
		target := strings.TrimSpace(trimmed[len("/daemon start "):])
		r.handleDaemonStartCommand(ctx, target)
		return true, false

	case lower == "/agents" || lower == "/agent list":
		r.handleAgentsListCommand()
		return true, false

	case strings.HasPrefix(lower, "/switch ") || strings.HasPrefix(lower, "/agent switch "):
		var target string
		if strings.HasPrefix(lower, "/switch ") {
			target = strings.TrimSpace(trimmed[len("/switch "):])
		} else {
			target = strings.TrimSpace(trimmed[len("/agent switch "):])
		}
		r.handleSwitchAgentCommand(target)
		return true, false

	case lower == "/switch":
		r.handleSwitchAgentCommand("")
		return true, false

	case strings.HasPrefix(lower, "/agent model ") || strings.HasPrefix(lower, "/model set "):
		var argStr string
		if strings.HasPrefix(lower, "/agent model ") {
			argStr = strings.TrimSpace(trimmed[len("/agent model "):])
		} else {
			argStr = strings.TrimSpace(trimmed[len("/model set "):])
		}
		r.handleAgentSetModelCommand(argStr)
		return true, false

	case lower == "/models" || lower == "/model list":
		r.handleModelsListCommand(ctx)
		return true, false

	case strings.HasPrefix(lower, "/agent enable "):
		target := strings.TrimSpace(trimmed[len("/agent enable "):])
		r.handleAgentToggleCommand(target, true)
		return true, false

	case strings.HasPrefix(lower, "/agent disable "):
		target := strings.TrimSpace(trimmed[len("/agent disable "):])
		r.handleAgentToggleCommand(target, false)
		return true, false

	default:
		if strings.HasPrefix(lower, "/") {
			fmt.Fprintf(r.out, "%s Unknown command: %s. Type /help for available commands.\n", ErrorStyle.Render("❌"), trimmed)
			return true, false
		}
		return false, false
	}
}

func (r *TerminalREPL) handleStatusCommand() {
	var mem runtime.MemStats
	runtime.ReadMemStats(&mem)

	daemonCount := 0
	if r.daemonProvider != nil {
		daemonCount = len(r.daemonProvider.ListDaemons())
	}

	text := fmt.Sprintf("\n%s\n"+
		"  • Active Session:  %s\n"+
		"  • Goroutines:      %d active\n"+
		"  • Memory Alloc:    %.2f MB (Sys: %.2f MB, GC cycles: %d)\n"+
		"  • Gateway Hub:     Live telemetry active\n"+
		"  • Daemons:         %d registered\n\n",
		BrandStyle.Render("📊 SYSTEM STATUS & VITALS:"),
		r.sessionID,
		runtime.NumGoroutine(),
		float64(mem.Alloc)/(1024*1024),
		float64(mem.Sys)/(1024*1024),
		mem.NumGC,
		daemonCount,
	)
	fmt.Fprint(r.out, text)
}

func (r *TerminalREPL) handleDaemonListCommand() {
	if r.daemonProvider == nil {
		fmt.Fprintln(r.out, DimStyle.Render("No background daemon supervisor attached."))
		return
	}
	daemons := r.daemonProvider.ListDaemons()
	var b strings.Builder
	b.WriteString(BrandStyle.Render("\n⚙️  SYSTEM BACKGROUND DAEMONS STATUS:\n"))
	b.WriteString(DimStyle.Render(strings.Repeat("─", 68)) + "\n")
	for _, d := range daemons {
		activeDot := SuccessStyle.Render("●")
		if !d.Active {
			activeDot = DimStyle.Render("○")
		}
		stateStr := fmt.Sprintf("[%-8s]", d.State)
		if d.Active {
			stateStr = SuccessStyle.Render(stateStr)
		} else {
			stateStr = DimStyle.Render(stateStr)
		}
		b.WriteString(fmt.Sprintf("  %s %-18s %s %s\n", activeDot, d.Name, stateStr, DimStyle.Render(d.Detail)))
	}
	b.WriteString(DimStyle.Render(strings.Repeat("─", 68)) + "\n")
	b.WriteString(DimStyle.Render("Commands: /daemon restart <name> • /daemon stop <name> • /daemon start <name>\n\n"))
	fmt.Fprint(r.out, b.String())
}

func (r *TerminalREPL) handleDaemonRestartCommand(ctx context.Context, name string) {
	if r.daemonProvider == nil {
		fmt.Fprintln(r.out, ErrorStyle.Render("❌ Error: Daemon provider not attached."))
		return
	}
	if err := r.daemonProvider.RestartDaemon(ctx, name); err != nil {
		fmt.Fprintf(r.out, "%s Failed to restart daemon %q: %v\n", ErrorStyle.Render("❌"), name, err)
	} else {
		fmt.Fprintf(r.out, "%s Daemon %q restarted successfully.\n", SuccessStyle.Render("✔"), name)
	}
}

func (r *TerminalREPL) handleDaemonStopCommand(ctx context.Context, name string) {
	if r.daemonProvider == nil {
		fmt.Fprintln(r.out, ErrorStyle.Render("❌ Error: Daemon provider not attached."))
		return
	}
	if err := r.daemonProvider.StopDaemon(ctx, name); err != nil {
		fmt.Fprintf(r.out, "%s Failed to stop daemon %q: %v\n", ErrorStyle.Render("❌"), name, err)
	} else {
		fmt.Fprintf(r.out, "%s Daemon %q stopped.\n", SuccessStyle.Render("✔"), name)
	}
}

func (r *TerminalREPL) handleDaemonStartCommand(ctx context.Context, name string) {
	if r.daemonProvider == nil {
		fmt.Fprintln(r.out, ErrorStyle.Render("❌ Error: Daemon provider not attached."))
		return
	}
	if err := r.daemonProvider.StartDaemon(ctx, name); err != nil {
		fmt.Fprintf(r.out, "%s Failed to start daemon %q: %v\n", ErrorStyle.Render("❌"), name, err)
	} else {
		fmt.Fprintf(r.out, "%s Daemon %q started.\n", SuccessStyle.Render("✔"), name)
	}
}

func (r *TerminalREPL) handleAgentsListCommand() {
	if r.gw == nil {
		fmt.Fprintln(r.out, ErrorStyle.Render("❌ Error: Gateway not attached."))
		return
	}
	catalog, err := r.gw.GetAgentCatalog()
	if err != nil {
		fmt.Fprintf(r.out, "%s Failed to load agent catalog: %v\n", ErrorStyle.Render("❌"), err)
		return
	}

	var b strings.Builder
	b.WriteString(BrandStyle.Render(fmt.Sprintf("\n🤖 REGISTERED AGENT SWARM CATALOG (%d Total, %d Active):\n",
		catalog.TotalAgents, catalog.ActiveAgents)))
	b.WriteString(DimStyle.Render(strings.Repeat("─", 74)) + "\n")

	keys := make([]string, 0, len(catalog.Agents))
	for k := range catalog.Agents {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	for _, k := range keys {
		ag := catalog.Agents[k]
		statusStr := "[ACTIVE  ]"
		if !ag.Enabled {
			statusStr = "[DISABLED]"
			statusStr = DimStyle.Render(statusStr)
		} else {
			statusStr = SuccessStyle.Render(statusStr)
		}
		coreTag := ""
		if ag.IsCore {
			coreTag = AgentStyle.Render("[CORE PLANNER]")
		}
		activeSwitchTag := ""
		if strings.EqualFold(r.activeAgent, k) {
			activeSwitchTag = SuccessStyle.Render("◄ [CURRENT ACTIVE]")
		} else if (r.activeAgent == "" || r.activeAgent == "auto") && ag.IsCore {
			activeSwitchTag = DimStyle.Render("◄ [DEFAULT AUTO]")
		}

		b.WriteString(fmt.Sprintf("  • @%-14s %s model:%-24s %s %s\n",
			ag.Identifier, statusStr, ag.AssignedModel, coreTag, activeSwitchTag))
		if len(ag.DeclaredTools) > 0 {
			b.WriteString(fmt.Sprintf("      %s %s\n",
				DimStyle.Render(fmt.Sprintf("tools (%d):", len(ag.DeclaredTools))),
				DimStyle.Render(strings.Join(ag.DeclaredTools, ", "))))
		}
	}
	b.WriteString(DimStyle.Render(strings.Repeat("─", 74)) + "\n")
	b.WriteString(DimStyle.Render("Switch: '/switch <agent>' (or '/switch auto') • Model: '/agent model <id> <model>' • List: '/models'\n\n"))
	fmt.Fprint(r.out, b.String())
}

func (r *TerminalREPL) handleSwitchAgentCommand(target string) {
	clean := strings.ToLower(strings.TrimPrefix(strings.TrimSpace(target), "@"))
	if clean == "" {
		current := r.activeAgent
		if current == "" {
			current = "auto (Manager Cognitive Planner)"
		}
		fmt.Fprintf(r.out, "Currently active agent targeting: %s\nUsage: /switch <agent> (e.g. /switch browser, /switch system, /switch auto)\n",
			AgentBadge(current))
		return
	}

	if clean == "auto" || clean == "manager" || clean == "reset" || clean == "default" {
		r.activeAgent = ""
		if r.gw != nil {
			_ = r.gw.SetActiveAgent(r.sessionID, "")
		}
		fmt.Fprintf(r.out, "%s Switched session to %s automatic planner mode.\n",
			SuccessStyle.Render("✔"), AgentStyle.Render("manager"))
		return
	}

	if r.gw != nil {
		catalog, err := r.gw.GetAgentCatalog()
		if err != nil {
			fmt.Fprintf(r.out, "%s Failed to load catalog: %v\n", ErrorStyle.Render("❌"), err)
			return
		}
		ag, ok := catalog.Agents[clean]
		if !ok {
			fmt.Fprintf(r.out, "%s Unknown agent %q. Available: system, browser, research, productivity, memory, manager\n",
				ErrorStyle.Render("❌"), clean)
			return
		}
		if !ag.Enabled {
			fmt.Fprintf(r.out, "%s Agent @%s is currently disabled. Enabling it now...\n", DimStyle.Render("ℹ"), clean)
			_ = r.gw.SetAgentStatus(clean, true)
		}
		if err := r.gw.SetActiveAgent(r.sessionID, clean); err != nil {
			fmt.Fprintf(r.out, "%s Failed to switch agent: %v\n", ErrorStyle.Render("❌"), err)
			return
		}
		r.activeAgent = clean
		fmt.Fprintf(r.out, "%s Switched active agent to %s (assigned model: %s).\n   Subsequent prompts will target @%s directly. Use '/switch auto' to return to manager planning.\n",
			SuccessStyle.Render("✔"), AgentBadge(clean), ag.AssignedModel, clean)
	} else {
		r.activeAgent = clean
		fmt.Fprintf(r.out, "%s Switched active agent to @%s.\n", SuccessStyle.Render("✔"), clean)
	}
}

func (r *TerminalREPL) handleAgentSetModelCommand(argStr string) {
	if r.gw == nil {
		fmt.Fprintln(r.out, ErrorStyle.Render("❌ Error: Gateway not attached."))
		return
	}
	fields := strings.Fields(argStr)
	if len(fields) < 2 {
		fmt.Fprintln(r.out, "Usage: /agent model <agent_id> <model_name>")
		fmt.Fprintln(r.out, "Example: /agent model manager gemini-2.5-flash")
		return
	}
	agentID := strings.TrimPrefix(fields[0], "@")
	modelName := fields[1]

	if err := r.gw.UpdateAgentModel(agentID, modelName); err != nil {
		fmt.Fprintf(r.out, "%s Failed to update model: %v\n", ErrorStyle.Render("❌"), err)
		return
	}
	fmt.Fprintf(r.out, "%s Updated assigned model for @%s to %s in config/agents.json\n",
		SuccessStyle.Render("✔"), agentID, AgentStyle.Render(modelName))
}

func (r *TerminalREPL) handleModelsListCommand(ctx context.Context) {
	if r.gw == nil {
		fmt.Fprintln(r.out, ErrorStyle.Render("❌ Error: Gateway not attached."))
		return
	}
	fmt.Fprintln(r.out, DimStyle.Render("Connecting to Google GenAI via google.golang.org/genai..."))
	models, err := r.gw.ListAvailableModels(ctx, false)
	if err != nil {
		fmt.Fprintf(r.out, "%s Failed to fetch models: %v\n", ErrorStyle.Render("❌"), err)
		return
	}
	fmt.Fprint(r.out, RenderModelsCatalog(models))
}

func (r *TerminalREPL) handleAgentToggleCommand(agentID string, enable bool) {
	if r.gw == nil {
		fmt.Fprintln(r.out, ErrorStyle.Render("❌ Error: Gateway not attached."))
		return
	}
	if err := r.gw.SetAgentStatus(agentID, enable); err != nil {
		fmt.Fprintf(r.out, "%s Failed to update agent %q: %v\n", ErrorStyle.Render("❌"), agentID, err)
	} else {
		state := "enabled"
		if !enable {
			state = "disabled"
		}
		fmt.Fprintf(r.out, "%s Agent @%s is now %s.\n", SuccessStyle.Render("✔"), agentID, state)
	}
}

func (r *TerminalREPL) executeInteractiveTurn(ctx context.Context, prompt string) {
	r.renderMu.Lock()
	defer r.renderMu.Unlock()

	turnCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(sigCh)

	go r.watchTurnInterrupt(turnCtx, sigCh, cancel)

	fmt.Fprint(r.out, RenderStatus("CLI", "Turn initiated. Connecting to control plane..."))

	rawReq := gateway.InboundTurnRequest{
		SessionID: r.sessionID,
		Channel:   gateway.ClientTypeCLI,
		Trigger:   gateway.TriggerInteractive,
		Prompt:    prompt,
	}
	if r.activeAgent != "" && r.activeAgent != "auto" {
		rawReq.TargetAgent = r.activeAgent
	}

	eventCh, req, err := r.gw.SubmitTurn(turnCtx, rawReq)
	if err != nil {
		if r.gw != nil && r.gw.IsQuotaExceeded(err.Error()) {
			r.handleQuotaLimitFallback(ctx, prompt, rawReq.TargetAgent, err.Error())
			return
		}
		fmt.Fprint(r.out, RenderError(err.Error()))
		return
	}

	turnErr := r.consumeTurnStream(turnCtx, eventCh)
	if turnErr != "" && r.gw != nil && r.gw.IsQuotaExceeded(turnErr) {
		r.handleQuotaLimitFallback(ctx, prompt, req.TargetAgent, turnErr)
	}
}

func (r *TerminalREPL) handleQuotaLimitFallback(ctx context.Context, prompt, targetAgent, errDetail string) {
	target := strings.ToLower(strings.TrimSpace(targetAgent))
	if target == "" || target == "auto" {
		target = "manager"
	}

	fallbackModels := []string{
		"gemini-2.5-flash",
		"gemini-2.5-pro",
		"gemini-2.5-flash-lite",
		"gemini-1.5-flash",
		"gemini-1.5-pro",
	}

	currentModel := "default"
	if r.gw != nil {
		catalog, err := r.gw.GetAgentCatalog()
		if err == nil {
			if ag, ok := catalog.Agents[target]; ok {
				currentModel = ag.AssignedModel
			}
		}
	}

	fmt.Fprint(r.out, RenderQuotaFallbackPrompt(currentModel, target, fallbackModels))

	line, err := r.reader.ReadString('\n')
	if err != nil {
		return
	}
	choice := strings.TrimSpace(line)
	if choice == "" || strings.EqualFold(choice, "c") || strings.EqualFold(choice, "cancel") || strings.EqualFold(choice, "n") {
		fmt.Fprintln(r.out, DimStyle.Render("Fallback cancelled. Prompt not retried."))
		return
	}

	var selectedModel string
	var idx int
	if n, _ := fmt.Sscanf(choice, "%d", &idx); n == 1 && idx >= 1 && idx <= len(fallbackModels) {
		selectedModel = fallbackModels[idx-1]
	} else {
		selectedModel = choice
	}

	if !strings.Contains(selectedModel, ":") {
		selectedModel = "google:" + selectedModel
	}

	fmt.Fprintf(r.out, "%s Switching @%s model to %s and retrying prompt...\n\n",
		SuccessStyle.Render("✔"), target, AgentStyle.Render(selectedModel))

	if r.gw != nil {
		if err := r.gw.UpdateAgentModel(target, selectedModel); err != nil {
			fmt.Fprintf(r.out, "%s Failed to update model: %v\n", ErrorStyle.Render("❌"), err)
			return
		}
	}

	// Re-execute turn with the exact same prompt
	r.executeInteractiveTurn(ctx, prompt)
}

func (r *TerminalREPL) renderAutonomousTurn(req gateway.InboundTurnRequest, eventCh <-chan gateway.OutboundEvent) {
	r.renderMu.Lock()
	defer r.renderMu.Unlock()

	// Clear active prompt line
	fmt.Fprint(r.out, "\r\033[K\n")

	border := strings.Repeat("─", 68)
	fmt.Fprintln(r.out, BrandStyle.Render(border))
	fmt.Fprintln(r.out, BrandStyle.Render("📬 [GMAIL WATCHER] Autonomous Inbound Event"))

	from := extractHeader(req.Prompt, "From: ")
	subject := extractHeader(req.Prompt, "Subject: ")
	if from != "" {
		fmt.Fprintf(r.out, "   %s %s\n", DimStyle.Render("From:   "), from)
	}
	if subject != "" {
		fmt.Fprintf(r.out, "   %s %s\n", DimStyle.Render("Subject:"), subject)
	}
	fmt.Fprintln(r.out, BrandStyle.Render(border))

	streamRenderer := NewStreamRenderer(r.out)
	for ev := range eventCh {
		if ev.Type == gateway.EventHITLRequest {
			streamRenderer.Flush()
			r.handleHITLPrompt(context.Background(), ev.HITL)
		} else {
			streamRenderer.RenderEvent(ev)
		}
	}
	streamRenderer.Flush()

	fmt.Fprintln(r.out, BrandStyle.Render(border))
	fmt.Fprint(r.out, BrandStyle.Render("assistant > "))
}

func extractHeader(prompt, prefix string) string {
	for _, line := range strings.Split(prompt, "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, prefix) {
			return strings.TrimSpace(strings.TrimPrefix(trimmed, prefix))
		}
	}
	return ""
}

func (r *TerminalREPL) watchTurnInterrupt(ctx context.Context, sigCh <-chan os.Signal, cancel context.CancelFunc) {
	select {
	case <-ctx.Done():
		return
	case <-sigCh:
		fmt.Fprintln(r.out, ErrorStyle.Render("\n[Turn cancelled by user]"))
		cancel()
	}
}

func (r *TerminalREPL) consumeTurnStream(ctx context.Context, eventCh <-chan gateway.OutboundEvent) string {
	streamRenderer := NewStreamRenderer(r.out)
	defer streamRenderer.Flush()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	lastActivity := time.Now()
	var lastErr string

	for {
		select {
		case <-ctx.Done():
			return lastErr
		case <-ticker.C:
			elapsed := time.Since(lastActivity).Truncate(time.Second)
			if elapsed >= 2*time.Second {
				streamRenderer.RenderHeartbeat(elapsed)
			}
		case ev, ok := <-eventCh:
			if !ok {
				return lastErr
			}
			lastActivity = time.Now()
			if ev.Type == gateway.EventHITLRequest {
				streamRenderer.Flush()
				r.handleHITLPrompt(ctx, ev.HITL)
			} else {
				if ev.Type == gateway.EventTurnError {
					lastErr = ev.Error
					if lastErr == "" {
						lastErr = ev.TextDelta
					}
				}
				streamRenderer.RenderEvent(ev)
			}
		}
	}
}

func (r *TerminalREPL) handleHITLPrompt(ctx context.Context, prompt *gateway.HITLApprovalPrompt) {
	if prompt == nil {
		return
	}
	fmt.Fprint(r.out, RenderHITLPrompt(prompt))

	line, err := r.reader.ReadString('\n')
	if err != nil {
		return
	}

	trimmed := strings.ToLower(strings.TrimSpace(line))
	approved := trimmed == "y" || trimmed == "yes"

	resp := gateway.HITLResponse{
		RequestID:   prompt.RequestID,
		SessionID:   r.sessionID,
		Approved:    approved,
		RespondedAt: time.Now().UTC(),
	}

	if err := r.gw.RespondHITL(ctx, resp); err != nil {
		fmt.Fprint(r.out, RenderError(fmt.Sprintf("Failed to submit approval: %v", err)))
	}
}

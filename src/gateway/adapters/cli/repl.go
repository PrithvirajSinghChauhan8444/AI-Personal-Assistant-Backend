package cli

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"assistant/src/gateway"
	"github.com/google/uuid"
)

// TerminalREPL coordinates interactive client sessions over terminal standard I/O.
type TerminalREPL struct {
	gw        *gateway.Gateway
	sessionID string
	reader    *bufio.Reader
	out       io.Writer
	renderMu  sync.Mutex
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

// Run starts the interactive prompt loop and processes turns until exit.
func (r *TerminalREPL) Run(ctx context.Context) error {
	fmt.Fprint(r.out, RenderBanner(r.sessionID))

	// Register autonomous consumer to stream watcher events into terminal cleanly
	r.gw.RegisterAutonomousConsumer(r.sessionID, func(req gateway.InboundTurnRequest, eventCh <-chan gateway.OutboundEvent) {
		r.renderAutonomousTurn(req, eventCh)
	})
	defer r.gw.UnregisterAutonomousConsumer(r.sessionID)

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		promptText, err := r.readPrompt()
		if err != nil {
			if err == io.EOF {
				return nil
			}
			return err
		}

		if promptText == "" {
			continue
		}

		handled, shouldExit := r.handleSlashCommand(promptText)
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
	fmt.Fprint(r.out, BrandStyle.Render("assistant > "))
	line, err := r.reader.ReadString('\n')
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(line), nil
}

func (r *TerminalREPL) handleSlashCommand(input string) (handled bool, shouldExit bool) {
	switch strings.ToLower(input) {
	case "/exit", "/quit":
		fmt.Fprintln(r.out, "\nGoodbye.")
		return true, true
	case "/help":
		fmt.Fprint(r.out, RenderHelp())
		return true, false
	case "/clear":
		fmt.Fprint(r.out, "\033[H\033[2J")
		return true, false
	case "/session":
		fmt.Fprintf(r.out, "Active Session ID: %s\n", r.sessionID)
		return true, false
	default:
		return false, false
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

	go r.watchTurnInterrupt(sigCh, cancel)

	fmt.Fprint(r.out, RenderStatus("CLI", "Turn initiated. Connecting to control plane..."))

	rawReq := gateway.InboundTurnRequest{
		SessionID: r.sessionID,
		Channel:   gateway.ClientTypeCLI,
		Trigger:   gateway.TriggerInteractive,
		Prompt:    prompt,
	}

	eventCh, _, err := r.gw.SubmitTurn(turnCtx, rawReq)
	if err != nil {
		fmt.Fprint(r.out, RenderError(err.Error()))
		return
	}

	r.consumeTurnStream(turnCtx, eventCh)
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

func (r *TerminalREPL) watchTurnInterrupt(sigCh <-chan os.Signal, cancel context.CancelFunc) {
	select {
	case <-sigCh:
		fmt.Fprintln(r.out, ErrorStyle.Render("\n[Turn cancelled by user]"))
		cancel()
	}
}

func (r *TerminalREPL) consumeTurnStream(ctx context.Context, eventCh <-chan gateway.OutboundEvent) {
	streamRenderer := NewStreamRenderer(r.out)
	defer streamRenderer.Flush()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	lastActivity := time.Now()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			elapsed := time.Since(lastActivity).Truncate(time.Second)
			if elapsed >= 2*time.Second {
				streamRenderer.RenderHeartbeat(elapsed)
			}
		case ev, ok := <-eventCh:
			if !ok {
				return
			}
			lastActivity = time.Now()
			if ev.Type == gateway.EventHITLRequest {
				streamRenderer.Flush()
				r.handleHITLPrompt(ctx, ev.HITL)
			} else {
				streamRenderer.RenderEvent(ev)
			}
		}
	}
}

func (r *TerminalREPL) dispatchRenderEvent(ctx context.Context, ev gateway.OutboundEvent) {
	if ev.Type == gateway.EventHITLRequest {
		r.handleHITLPrompt(ctx, ev.HITL)
		return
	}
	renderer := NewStreamRenderer(r.out)
	renderer.RenderEvent(ev)
	renderer.Flush()
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

package cli

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"strings"
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
	turnCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(sigCh)

	go r.watchTurnInterrupt(sigCh, cancel)

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

func (r *TerminalREPL) watchTurnInterrupt(sigCh <-chan os.Signal, cancel context.CancelFunc) {
	select {
	case <-sigCh:
		fmt.Fprintln(r.out, ErrorStyle.Render("\n[Turn cancelled by user]"))
		cancel()
	}
}

func (r *TerminalREPL) consumeTurnStream(ctx context.Context, eventCh <-chan gateway.OutboundEvent) {
	for {
		select {
		case <-ctx.Done():
			return
		case ev, ok := <-eventCh:
			if !ok {
				return
			}
			r.dispatchRenderEvent(ctx, ev)
		}
	}
}

func (r *TerminalREPL) dispatchRenderEvent(ctx context.Context, ev gateway.OutboundEvent) {
	switch ev.Type {
	case gateway.EventTokenChunk:
		fmt.Fprint(r.out, ev.TextDelta)
	case gateway.EventThoughtChunk:
		fmt.Fprintln(r.out, RenderThought(ev.AgentName, ev.TextDelta))
	case gateway.EventStatusUpdate:
		fmt.Fprint(r.out, RenderStatus(ev.AgentName, ev.StatusMsg))
	case gateway.EventHITLRequest:
		r.handleHITLPrompt(ctx, ev.HITL)
	case gateway.EventTurnComplete:
		fmt.Fprint(r.out, RenderTurnMetrics(ev.Metrics))
	case gateway.EventTurnError:
		fmt.Fprint(r.out, RenderError(ev.Error))
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

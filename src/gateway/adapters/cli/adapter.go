package cli

import (
	"context"
	"fmt"
	"io"
	"os"
	"time"

	"assistant/src/gateway"
	"github.com/google/uuid"
)

// CLIAdapter manages interactive terminal sessions and one-off turn runs.
type CLIAdapter struct {
	gw        *gateway.Gateway
	sessionID string
	in        io.Reader
	out       io.Writer
}

// NewCLIAdapter creates an adapter targeting the specified I/O streams.
func NewCLIAdapter(gw *gateway.Gateway, in io.Reader, out io.Writer, sessionID string) *CLIAdapter {
	if in == nil {
		in = os.Stdin
	}
	if out == nil {
		out = os.Stdout
	}
	if sessionID == "" {
		sessionID = uuid.NewString()
	}
	return &CLIAdapter{
		gw:        gw,
		sessionID: sessionID,
		in:        in,
		out:       out,
	}
}

// StartInteractive launches the full terminal REPL session.
func (a *CLIAdapter) StartInteractive(ctx context.Context) error {
	repl := NewTerminalREPL(a.gw, a.in, a.out, a.sessionID)
	return repl.Run(ctx)
}

// RunSingleTurn executes a single turn request to completion and streams output.
func RunSingleTurn(ctx context.Context, gw *gateway.Gateway, rawReq gateway.InboundTurnRequest, out io.Writer) error {
	fmt.Fprint(out, RenderStatus("CLI", "Turn initiated. Connecting to control plane..."))

	eventCh, _, err := gw.SubmitTurn(ctx, rawReq)
	if err != nil {
		return fmt.Errorf("single turn submission failed: %w", err)
	}

	streamRenderer := NewStreamRenderer(out)
	defer streamRenderer.Flush()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	lastActivity := time.Now()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			elapsed := time.Since(lastActivity).Truncate(time.Second)
			if elapsed >= 2*time.Second {
				streamRenderer.RenderHeartbeat(elapsed)
			}
		case ev, ok := <-eventCh:
			if !ok {
				return nil
			}
			lastActivity = time.Now()
			streamRenderer.RenderEvent(ev)
		}
	}
}

func renderSingleEvent(out io.Writer, ev gateway.OutboundEvent) {
	renderer := NewStreamRenderer(out)
	renderer.RenderEvent(ev)
	renderer.Flush()
}

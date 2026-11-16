package cli

import (
	"context"
	"fmt"
	"io"
	"os"
	"time"

	"assistant/src/gateway"
	"github.com/google/uuid"
	"github.com/mattn/go-isatty"
)

// DaemonStatus represents the operational status of a background service.
type DaemonStatus struct {
	Name   string
	State  string // "RUNNING", "WATCHING", "SYNCED", "STOPPED", "DISABLED", "IDLE"
	Detail string
	Active bool
}

// DaemonProvider exposes lifecycle operations and health inspection for background daemons.
type DaemonProvider interface {
	ListDaemons() []DaemonStatus
	RestartDaemon(ctx context.Context, name string) error
	StopDaemon(ctx context.Context, name string) error
	StartDaemon(ctx context.Context, name string) error
}

// CLIAdapter manages interactive terminal sessions and one-off turn runs.
type CLIAdapter struct {
	gw             *gateway.Gateway
	sessionID      string
	in             io.Reader
	out            io.Writer
	daemonProvider DaemonProvider
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

// SetDaemonProvider attaches a daemon supervisor provider to the CLI adapter.
func (a *CLIAdapter) SetDaemonProvider(dp DaemonProvider) {
	a.daemonProvider = dp
}

// StartInteractive launches the full terminal TUI session, with fallback to line REPL.
func (a *CLIAdapter) StartInteractive(ctx context.Context) error {
	// Check if environment requests plain REPL or if running non-interactively
	if os.Getenv("ASSISTANT_PLAIN") == "1" || os.Getenv("TERM") == "dumb" || !isTerminalDevice(a.in, a.out) {
		repl := NewTerminalREPL(a.gw, a.in, a.out, a.sessionID)
		return repl.Run(ctx)
	}

	tui := NewTUI(a.gw, a.sessionID)
	tui.SetDaemonProvider(a.daemonProvider)
	return tui.Run(ctx)
}

func isTerminalDevice(in io.Reader, out io.Writer) bool {
	inFile, inOk := in.(*os.File)
	outFile, outOk := out.(*os.File)
	if !inOk || !outOk {
		return false
	}
	return isatty.IsTerminal(inFile.Fd()) && isatty.IsTerminal(outFile.Fd())
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

package tui

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"

	"assistant/src/gateway"
	"github.com/google/uuid"
	"golang.org/x/term"
)

// TUIAdapter coordinates an interactive dual-pane terminal user interface.
type TUIAdapter struct {
	gw             *gateway.Gateway
	sessionID      string
	in             io.Reader
	out            io.Writer
	state          *UIState
	engine         *SuggestionEngine
	demuxer        *EventDemuxer
	daemonProvider DaemonProvider
	cancelActive   context.CancelFunc
	renderMu       sync.Mutex
	redrawCh       chan struct{}
}

// NewTUIAdapter instantiates the standalone TUI adapter.
func NewTUIAdapter(gw *gateway.Gateway, in io.Reader, out io.Writer, sessionID string) *TUIAdapter {
	if sessionID == "" {
		sessionID = uuid.NewString()
	}
	if in == nil {
		in = os.Stdin
	}
	if out == nil {
		out = os.Stdout
	}

	state := NewUIState(sessionID)
	demuxer := NewEventDemuxer(state)

	var agents []string
	if gw != nil {
		if catalog, err := gw.GetAgentCatalog(); err == nil {
			for name := range catalog.Agents {
				agents = append(agents, name)
			}
		}
	}
	if len(agents) == 0 {
		agents = []string{"system", "browser", "research", "productivity", "memory"}
	}

	engine := NewSuggestionEngine(agents)

	return &TUIAdapter{
		gw:        gw,
		sessionID: sessionID,
		in:        in,
		out:       out,
		state:     state,
		engine:    engine,
		demuxer:   demuxer,
		redrawCh:  make(chan struct{}, 10),
	}
}

// SetDaemonProvider binds the background daemon supervisor provider to the adapter.
func (a *TUIAdapter) SetDaemonProvider(dp DaemonProvider) {
	a.daemonProvider = dp
}

// StartInteractive launches raw terminal mode and runs the full reactive event loop.
func (a *TUIAdapter) StartInteractive(ctx context.Context) error {
	file, ok := a.in.(*os.File)
	if !ok || !term.IsTerminal(int(file.Fd())) {
		return errors.New("tui adapter requires an interactive TTY input")
	}
	fd := int(file.Fd())

	// 1. Enter alternate screen and hide cursor during initial setup
	fmt.Fprint(a.out, "\033[?1049h\033[?25h")

	// 2. Put terminal into raw mode
	oldState, err := term.MakeRaw(fd)
	if err != nil {
		return fmt.Errorf("failed to initialize raw terminal mode: %w", err)
	}

	// 3. Guaranteed terminal restore on every possible exit path
	defer func() {
		_ = term.Restore(fd, oldState)
		fmt.Fprint(a.out, "\033[?25h\033[?1049l") // show cursor & leave alt screen
	}()

	// Window resize notification
	sigWin := make(chan os.Signal, 1)
	signal.Notify(sigWin, syscall.SIGWINCH)
	defer signal.Stop(sigWin)

	// Register autonomous watcher consumer
	if a.gw != nil {
		a.gw.RegisterAutonomousConsumer(a.sessionID, func(req gateway.InboundTurnRequest, eventCh <-chan gateway.OutboundEvent) {
			a.consumeTurnStream(ctx, eventCh)
		})
		defer a.gw.UnregisterAutonomousConsumer(a.sessionID)
	}

	a.updateTerminalSize(fd)
	a.triggerRedraw()

	// Redraw worker
	redrawCtx, cancelRedraw := context.WithCancel(ctx)
	defer cancelRedraw()
	go a.redrawLoop(redrawCtx)

	return a.readInputLoop(ctx, fd, sigWin)
}

func (a *TUIAdapter) updateTerminalSize(fd int) {
	w, h, err := term.GetSize(fd)
	if err == nil {
		a.state.mu.Lock()
		a.state.Width = w
		a.state.Height = h
		a.state.mu.Unlock()
	}
}

func (a *TUIAdapter) triggerRedraw() {
	select {
	case a.redrawCh <- struct{}{}:
	default:
	}
}

func (a *TUIAdapter) redrawLoop(ctx context.Context) {
	ticker := time.NewTicker(80 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-a.redrawCh:
			a.drawFrame()
		case <-ticker.C:
			a.state.mu.Lock()
			isGen := a.state.IsGenerating
			a.state.mu.Unlock()
			if isGen {
				a.drawFrame()
			}
		}
	}
}

func (a *TUIAdapter) drawFrame() {
	a.renderMu.Lock()
	defer a.renderMu.Unlock()

	result := RenderScreen(a.state)
	// Draw screen from top-left, then position physical cursor
	cursorSeq := fmt.Sprintf("\033[%d;%dH", result.CursorRow, result.CursorCol)
	fmt.Fprint(a.out, "\033[H"+result.Screen+cursorSeq)
}

func (a *TUIAdapter) readInputLoop(ctx context.Context, fd int, sigWin <-chan os.Signal) error {
	buf := make([]byte, 32)
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-sigWin:
			a.updateTerminalSize(fd)
			a.triggerRedraw()
		default:
			n, err := a.in.Read(buf)
			if err != nil {
				if errors.Is(err, io.EOF) {
					return nil
				}
				return err
			}
			if n > 0 {
				shouldExit := a.handleRawInput(ctx, buf[:n])
				if shouldExit {
					return nil
				}
				a.triggerRedraw()
			}
		}
	}
}

func (a *TUIAdapter) handleRawInput(ctx context.Context, b []byte) (shouldExit bool) {
	// Ctrl+C (0x03)
	if len(b) == 1 && b[0] == 3 {
		if a.cancelActive != nil {
			a.cancelActive()
			a.cancelActive = nil
			a.state.AppendLog("SYS", "User cancelled running turn (Ctrl+C)", false)
			return false
		}
		if len(a.state.InputBuffer) > 0 {
			a.state.InputBuffer = nil
			a.state.CursorPos = 0
			a.state.IsSuggestVisible = false
			return false
		}
		return true // Exit on second Ctrl+C
	}

	// Ctrl+L (0x0C) - Toggle logs pane
	if len(b) == 1 && b[0] == 12 {
		a.state.ShowLogsPane = !a.state.ShowLogsPane
		return false
	}

	// Ctrl+U (0x15) - Clear input line
	if len(b) == 1 && b[0] == 21 {
		a.state.InputBuffer = nil
		a.state.CursorPos = 0
		a.state.IsSuggestVisible = false
		return false
	}

	// Ctrl+W (0x17) - Delete word backwards
	if len(b) == 1 && b[0] == 23 {
		a.deleteWordBackwards()
		return false
	}

	// Escape sequences (Arrows, PageUp, PageDown, Home, End)
	if b[0] == 27 {
		if len(b) == 1 {
			// Lone Esc: dismiss suggestions
			a.state.IsSuggestVisible = false
			return false
		}
		return a.handleEscapeSequence(b)
	}

	// Enter (0x0D or 0x0A)
	if b[0] == 13 || b[0] == 10 {
		return a.handleEnter(ctx)
	}

	// Tab (0x09) - Accept suggestion
	if b[0] == 9 {
		a.acceptCurrentSuggestion()
		return false
	}

	// Backspace (0x7F or 0x08)
	if b[0] == 127 || b[0] == 8 {
		a.handleBackspace()
		return false
	}

	// Normal typed text
	runes := []rune(string(b))
	for _, r := range runes {
		if r >= 32 {
			a.insertRune(r)
		}
	}
	a.updateSuggestions()
	return false
}

func (a *TUIAdapter) handleEscapeSequence(b []byte) bool {
	seq := string(b)
	switch seq {
	case "\033[A": // Up
		if a.state.IsSuggestVisible && len(a.state.Suggestions) > 0 {
			if a.state.SelectedSuggest > 0 {
				a.state.SelectedSuggest--
			}
		} else {
			a.navigateHistory(-1)
		}
	case "\033[B": // Down
		if a.state.IsSuggestVisible && len(a.state.Suggestions) > 0 {
			if a.state.SelectedSuggest < len(a.state.Suggestions)-1 {
				a.state.SelectedSuggest++
			}
		} else {
			a.navigateHistory(1)
		}
	case "\033[C": // Right
		if a.state.CursorPos < len(a.state.InputBuffer) {
			a.state.CursorPos++
			a.updateSuggestions()
		}
	case "\033[D": // Left
		if a.state.CursorPos > 0 {
			a.state.CursorPos--
			a.updateSuggestions()
		}
	case "\033[5~": // Page Up
		a.state.ResponseScroll += 5
	case "\033[6~": // Page Down
		if a.state.ResponseScroll >= 5 {
			a.state.ResponseScroll -= 5
		} else {
			a.state.ResponseScroll = 0
		}
	case "\033[H", "\033[1~": // Home
		a.state.CursorPos = 0
		a.updateSuggestions()
	case "\033[F", "\033[4~": // End
		a.state.CursorPos = len(a.state.InputBuffer)
		a.updateSuggestions()
	case "\033[3~": // Delete
		if a.state.CursorPos < len(a.state.InputBuffer) {
			a.state.InputBuffer = append(a.state.InputBuffer[:a.state.CursorPos], a.state.InputBuffer[a.state.CursorPos+1:]...)
			a.updateSuggestions()
		}
	}
	return false
}

func (a *TUIAdapter) handleEnter(ctx context.Context) (shouldExit bool) {
	if a.state.IsSuggestVisible && len(a.state.Suggestions) > 0 {
		a.acceptCurrentSuggestion()
		return false
	}

	prompt := strings.TrimSpace(string(a.state.InputBuffer))
	if prompt == "" {
		return false
	}

	a.state.ResetInput()

	// Check slash commands
	if strings.HasPrefix(prompt, "/") {
		return a.executeSlashCommand(ctx, prompt)
	}

	// Normal conversational turn
	a.submitTurn(ctx, prompt)
	return false
}

func (a *TUIAdapter) executeSlashCommand(ctx context.Context, cmd string) bool {
	lower := strings.ToLower(cmd)
	switch {
	case lower == "/exit" || lower == "/quit":
		return true

	case lower == "/clear":
		a.state.ConversationLines = nil
		a.state.ResponseScroll = 0
		a.state.AppendLog("SYS", "Conversation view cleared", false)

	case lower == "/status":
		var mem runtime.MemStats
		runtime.ReadMemStats(&mem)
		daemonCount := 0
		if a.daemonProvider != nil {
			daemonCount = len(a.daemonProvider.ListDaemons())
		}
		stat := fmt.Sprintf("Goroutines: %d | Mem: %.2fMB | Daemons: %d",
			runtime.NumGoroutine(), float64(mem.Alloc)/(1024*1024), daemonCount)
		a.state.ConversationLines = append(a.state.ConversationLines, "System Status: "+stat)
		a.state.AppendLog("STATUS", stat, false)

	case strings.HasPrefix(lower, "/switch"):
		target := strings.TrimSpace(strings.TrimPrefix(cmd, "/switch"))
		target = strings.TrimPrefix(target, "@")
		if target == "" || target == "auto" {
			target = "manager"
		}
		a.state.ActiveAgent = target
		if a.gw != nil {
			_ = a.gw.SetActiveAgent(a.sessionID, target)
		}
		msg := fmt.Sprintf("Switched active agent targeting to @%s", target)
		a.state.ConversationLines = append(a.state.ConversationLines, "Agent: "+msg)
		a.state.AppendLog("SYS", msg, false)

	case lower == "/daemons":
		if a.daemonProvider != nil {
			list := a.daemonProvider.ListDaemons()
			a.state.ConversationLines = append(a.state.ConversationLines, fmt.Sprintf("Background Daemons (%d registered):", len(list)))
			for _, d := range list {
				a.state.ConversationLines = append(a.state.ConversationLines, fmt.Sprintf("  • %-16s [%-8s] %s", d.Name, d.State, d.Detail))
			}
		} else {
			a.state.ConversationLines = append(a.state.ConversationLines, "No daemon provider attached.")
		}

	case lower == "/models":
		a.state.ConversationLines = append(a.state.ConversationLines, "Active Model: "+a.state.AssignedModel)
		a.state.AppendLog("SYS", "Active model assignment: "+a.state.AssignedModel, false)

	case lower == "/help":
		a.state.ConversationLines = append(a.state.ConversationLines,
			"Available Commands:",
			"  /status        Inspect system vitals and memory",
			"  /switch <name> Direct prompt to agent (e.g. /switch browser)",
			"  /daemons       Inspect background supervisor daemons",
			"  /models        Show model assignments",
			"  /clear         Clear response window",
			"  /exit          Quit assistant",
			"Keyboard Shortcuts:",
			"  Tab: Autocomplete suggestion   Ctrl+L: Toggle Logs pane",
			"  PgUp/PgDn: Scroll response     Ctrl+C: Cancel / Exit",
		)

	default:
		a.state.ConversationLines = append(a.state.ConversationLines, "Unknown command: "+cmd+" (Type /help for options)")
	}
	return false
}

func (a *TUIAdapter) submitTurn(ctx context.Context, prompt string) {
	if a.gw == nil {
		a.state.ConversationLines = append(a.state.ConversationLines, "User: "+prompt, "Error: Gateway not attached")
		return
	}

	a.state.ConversationLines = append(a.state.ConversationLines, "User: "+prompt)
	a.state.ResponseScroll = 0
	a.state.IsGenerating = true

	turnCtx, cancel := context.WithCancel(ctx)
	a.cancelActive = cancel

	rawReq := gateway.InboundTurnRequest{
		SessionID: a.sessionID,
		Channel:   gateway.ClientTypeCLI,
		Trigger:   gateway.TriggerInteractive,
		Prompt:    prompt,
	}
	if a.state.ActiveAgent != "" && a.state.ActiveAgent != "manager" {
		rawReq.TargetAgent = a.state.ActiveAgent
	}

	eventCh, _, err := a.gw.SubmitTurn(turnCtx, rawReq)
	if err != nil {
		a.state.IsGenerating = false
		a.state.ConversationLines = append(a.state.ConversationLines, "Error: "+err.Error())
		a.state.AppendLog("ERROR", err.Error(), true)
		return
	}

	go func() {
		defer cancel()
		a.consumeTurnStream(turnCtx, eventCh)
	}()
}

func (a *TUIAdapter) consumeTurnStream(ctx context.Context, eventCh <-chan gateway.OutboundEvent) {
	for {
		select {
		case <-ctx.Done():
			return
		case ev, ok := <-eventCh:
			if !ok {
				a.state.mu.Lock()
				a.state.IsGenerating = false
				a.state.mu.Unlock()
				a.triggerRedraw()
				return
			}
			a.demuxer.Process(ev)
			a.triggerRedraw()
		}
	}
}

func (a *TUIAdapter) insertRune(r rune) {
	idx := a.state.CursorPos
	a.state.InputBuffer = append(a.state.InputBuffer[:idx], append([]rune{r}, a.state.InputBuffer[idx:]...)...)
	a.state.CursorPos++
}

func (a *TUIAdapter) handleBackspace() {
	if a.state.CursorPos > 0 {
		idx := a.state.CursorPos - 1
		a.state.InputBuffer = append(a.state.InputBuffer[:idx], a.state.InputBuffer[idx+1:]...)
		a.state.CursorPos--
		a.updateSuggestions()
	}
}

func (a *TUIAdapter) deleteWordBackwards() {
	if a.state.CursorPos == 0 {
		return
	}
	start := a.state.CursorPos
	for start > 0 && a.state.InputBuffer[start-1] == ' ' {
		start--
	}
	for start > 0 && a.state.InputBuffer[start-1] != ' ' {
		start--
	}
	a.state.InputBuffer = append(a.state.InputBuffer[:start], a.state.InputBuffer[a.state.CursorPos:]...)
	a.state.CursorPos = start
	a.updateSuggestions()
}

func (a *TUIAdapter) updateSuggestions() {
	matches, prefix, wordStart := a.engine.Query(a.state.InputBuffer, a.state.CursorPos)
	a.state.Suggestions = matches
	a.state.ActivePrefix = prefix
	a.state.ActiveWordStart = wordStart
	a.state.IsSuggestVisible = len(matches) > 0
	if a.state.SelectedSuggest >= len(matches) {
		a.state.SelectedSuggest = 0
	}
}

func (a *TUIAdapter) acceptCurrentSuggestion() {
	if !a.state.IsSuggestVisible || len(a.state.Suggestions) == 0 {
		return
	}
	selected := a.state.Suggestions[a.state.SelectedSuggest]
	start := a.state.ActiveWordStart
	end := a.state.CursorPos

	replacement := []rune(selected.Token + " ")
	newBuf := append(a.state.InputBuffer[:start], append(replacement, a.state.InputBuffer[end:]...)...)

	a.state.InputBuffer = newBuf
	a.state.CursorPos = start + len(replacement)
	a.state.IsSuggestVisible = false
}

func (a *TUIAdapter) navigateHistory(delta int) {
	if len(a.state.History) == 0 {
		return
	}
	newIdx := a.state.HistoryIndex + delta
	if newIdx < 0 {
		newIdx = 0
	}
	if newIdx >= len(a.state.History) {
		a.state.HistoryIndex = len(a.state.History)
		a.state.InputBuffer = nil
		a.state.CursorPos = 0
		return
	}
	a.state.HistoryIndex = newIdx
	// Walk history from newest to oldest
	item := a.state.History[len(a.state.History)-1-newIdx]
	a.state.InputBuffer = []rune(item)
	a.state.CursorPos = len(a.state.InputBuffer)
}

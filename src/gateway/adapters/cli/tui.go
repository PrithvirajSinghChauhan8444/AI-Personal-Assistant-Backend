package cli

import (
	"context"
	"fmt"
	"runtime"
	"sort"
	"strings"
	"time"
	"unicode"

	"assistant/src/gateway"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Pane identifiers
const (
	PaneDaemons = 0 // Left sidepane: Always-running daemons & Help
	PaneClean   = 1 // Center pane: Task Stream (Less logging / clean summary)
	PaneRaw     = 2 // Right pane: Raw Telemetry Stream (Complete logs)
	numPanes    = 3
)

// Low-color monochrome palette styles with vibrant response accents
var (
	tuiBorderDim    = lipgloss.Color("#262B36")
	tuiBorderActive = lipgloss.Color("#CBD5E1")
	tuiText         = lipgloss.Color("#E2E8F0")
	tuiMuted        = lipgloss.Color("#8A96A8")
	tuiFaint        = lipgloss.Color("#525D70")
	tuiDotOk        = lipgloss.Color("#4ADE80")
	tuiDotIdle      = lipgloss.Color("#64748B")

	styleHeader = lipgloss.NewStyle().
			Foreground(tuiMuted).
			Background(lipgloss.Color("#11141C"))

	styleTitle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#FFFFFF"))

	stylePaneTitle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#FFFFFF"))

	stylePaneMeta = lipgloss.NewStyle().
			Foreground(tuiFaint)

	stylePromptLabel = lipgloss.NewStyle().
				Bold(true).
				Foreground(lipgloss.Color("#FFFFFF"))

	styleGhost = lipgloss.NewStyle().
			Foreground(tuiFaint)

	styleFaint = lipgloss.NewStyle().
			Foreground(tuiFaint)

	styleSuggRow = lipgloss.NewStyle().
			Padding(0, 1)

	styleSuggSelected = lipgloss.NewStyle().
				Background(lipgloss.Color("#262F40")).
				Foreground(lipgloss.Color("#FFFFFF")).
				Padding(0, 1)

	// Markdown typography & rich response colors
	styleH1         = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8"))
	styleH2         = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#67E8F9"))
	styleH3         = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#93C5FD"))
	styleH4         = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#A5B4FC"))
	styleBoldText   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F8FAFC"))
	styleKeyLabel   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8"))
	styleCodeSpan   = lipgloss.NewStyle().Foreground(lipgloss.Color("#FDE047")).Background(lipgloss.Color("#1E293B")).Padding(0, 1)
	styleBulletMain = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8"))
	styleBulletSub  = lipgloss.NewStyle().Foreground(lipgloss.Color("#94A3B8"))
	styleNumBadge   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#60A5FA"))
	styleLinkURL    = lipgloss.NewStyle().Underline(true).Foreground(lipgloss.Color("#60A5FA"))
	styleQuoteLine  = lipgloss.NewStyle().Foreground(lipgloss.Color("#94A3B8")).Italic(true)
	styleCodeBorder = lipgloss.NewStyle().Foreground(lipgloss.Color("#334155"))
	styleSuccessTag = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#4ADE80"))
	styleWarnTag    = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FBBF24"))
	styleErrorTag   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F87171"))
	styleStepArrow  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8"))
)

// SuggestionItem represents an autocomplete candidate.
type SuggestionItem struct {
	Token string
	Type  string // "cmd", "agent"
	Desc  string
}

// CleanEntry represents a human-readable turn item in the center pane.
type CleanEntry struct {
	Type       string // "user", "assistant", "system"
	Text       string
	Thought    string
	Steps      []string
	ResultPass bool
	ResultText string
	TimeStr    string
}

// RawLogEntry represents a complete diagnostic log line in the right pane.
type RawLogEntry struct {
	TimeStr string
	Level   string // "INFO", "DEBUG", "TOOL", "PIPE", "WARN", "ERROR"
	Message string
}

// Msg types for Bubble Tea event bridge
type turnEventMsg struct {
	ev gateway.OutboundEvent
}

type turnDoneMsg struct{}

type turnErrorMsg struct {
	err error
}

type autonomousReqMsg struct {
	req gateway.InboundTurnRequest
}

// TUIModel implements tea.Model for the terminal user interface.
type TUIModel struct {
	gw             *gateway.Gateway
	sessionID      string
	daemonProvider DaemonProvider
	ctx            context.Context

	// Dimensions
	width  int
	height int

	// Focus & Layout
	activePane   int    // PaneDaemons (0), PaneClean (1), PaneRaw (2)
	showSidepane bool   // Left sidepane visibility (toggle with Ctrl+D)
	maximized    int    // -1 if normal, or 0, 1, 2 when focused pane is zoomed (Ctrl+F)
	logFilter    string // "ALL", "TOOL", "PIPE", "DEBUG"
	filterIdx    int

	// Dynamic Agent & Daemon State
	agentCatalog *gateway.AgentCatalogSnapshot
	daemons      []DaemonStatus

	// Stream Panes Content
	cleanItems []CleanEntry
	rawLogs    []RawLogEntry

	// Independent scrolling state per pane
	scrollOffset       int // Active pane scroll offset (backward compatible with tests)
	cleanScrollOffset  int // Lines scrolled up in Task Stream (0 = live auto-scroll)
	rawScrollOffset    int // Lines scrolled up in Raw Telemetry (0 = live auto-scroll)
	daemonScrollOffset int // Lines scrolled down in Daemons sidepane (0 = top)
	maxScroll          int // Maximum lines that can be scrolled up for active pane
	maxCleanScroll     int
	maxRawScroll       int
	maxDaemonScroll    int

	// Pane 1 Interactive Navigation
	daemonSelectedIdx int // Index of selected item in Pane 1 (daemons, agents, cmds)

	// Command / Prompt History
	history    []string
	historyIdx int
	draftInput string

	// Input buffer (Rune-safe with visible cursor)
	input             string
	cursor            int // Rune offset (0 to len([]rune(input)))
	ghostText         string
	inputScrollOffset int // Viewport line scroll for multi-line inputs
	suggestions       []SuggestionItem
	suggIndex         int
	suggScroll        int
	suggOpen          bool

	// Active turn tracking
	executing   bool
	currentTurn *CleanEntry
	waitingHITL *gateway.HITLApprovalPrompt

	// Program handle for async events
	program *tea.Program
}

// NewTUIModel initializes a TUI model with live agent discovery and daemon integration.
func NewTUIModel(gw *gateway.Gateway, sessionID string, dp DaemonProvider, ctx context.Context) *TUIModel {
	m := &TUIModel{
		gw:             gw,
		sessionID:      sessionID,
		daemonProvider: dp,
		ctx:            ctx,
		activePane:     PaneClean, // Default focus to Center Clean Stream
		showSidepane:   true,      // Left sidepane visible by default
		maximized:      -1,
		width:          80,
		height:         24,
		logFilter:      "ALL",
		historyIdx:     -1,
		cleanItems: []CleanEntry{
			{
				Type:    "system",
				Text:    "Assistant initialized in session " + sessionID + ". Ready for input.",
				TimeStr: time.Now().Format("15:04:05"),
			},
		},
		rawLogs: []RawLogEntry{
			{
				TimeStr: time.Now().Format("15:04:05.000"),
				Level:   "INFO",
				Message: "Gateway core initialized (session: " + sessionID + ")",
			},
			{
				TimeStr: time.Now().Format("15:04:05.012"),
				Level:   "DEBUG",
				Message: "Terminal TUI loaded with live agent catalog & daemon provider",
			},
		},
	}

	// Fetch dynamic agents from gateway API
	m.reloadAgentCatalog()

	// Query real daemons from daemon supervisor
	m.refreshDaemons()

	return m
}

// Init initializes the Bubble Tea program.
func (m *TUIModel) Init() tea.Cmd {
	return nil
}

// SetProgram binds the tea.Program pointer so goroutines can dispatch messages.
func (m *TUIModel) SetProgram(p *tea.Program) {
	m.program = p
}

// reloadAgentCatalog fetches the live registered agents using Gateway.GetAgentCatalog().
func (m *TUIModel) reloadAgentCatalog() {
	if m.gw != nil {
		catalog, err := m.gw.GetAgentCatalog()
		if err == nil && catalog != nil {
			m.agentCatalog = catalog
		}
	}
	m.rebuildSuggestions()
}

// refreshDaemons queries active background services from the DaemonProvider.
func (m *TUIModel) refreshDaemons() {
	if m.daemonProvider != nil {
		m.daemons = m.daemonProvider.ListDaemons()
	} else {
		// Fallback default system components
		m.daemons = []DaemonStatus{
			{Name: "session-governor", State: "SYNCED", Detail: "SQLite session timeline", Active: true},
			{Name: "priority-queue", State: "ACTIVE", Detail: "turn queue multiplexer", Active: true},
			{Name: "py-bridge-pipe", State: "ACTIVE", Detail: "Layer 4 anonymous stdio", Active: true},
		}
	}
}

// rebuildSuggestions populates commands and dynamically discovered agents.
func (m *TUIModel) rebuildSuggestions() {
	var list []SuggestionItem

	// 1. Built-in Core Commands
	list = append(list,
		SuggestionItem{Token: "/plan", Type: "cmd", Desc: "Build task DAG without tool execution"},
		SuggestionItem{Token: "/run", Type: "cmd", Desc: "Full execution saga (plan, dispatch, verify)"},
		SuggestionItem{Token: "/daemon", Type: "cmd", Desc: "Inspect and manage background daemons"},
		SuggestionItem{Token: "/agents", Type: "cmd", Desc: "List registered specialist agents & models"},
		SuggestionItem{Token: "/agent", Type: "cmd", Desc: "Manage agents (enable/disable <id>)"},
		SuggestionItem{Token: "/status", Type: "cmd", Desc: "Display bridge latency, RAM, and goroutines"},
		SuggestionItem{Token: "/checkpoint", Type: "cmd", Desc: "Commit memory snapshot to SQLite DB"},
		SuggestionItem{Token: "/clear", Type: "cmd", Desc: "Clear terminal stream buffers"},
		SuggestionItem{Token: "/help", Type: "cmd", Desc: "Display keyboard commands and shortcuts"},
		SuggestionItem{Token: "/session", Type: "cmd", Desc: "Show active session ID"},
		SuggestionItem{Token: "/exit", Type: "cmd", Desc: "Quit assistant"},
	)

	// 2. Dynamic Agents from Gateway Catalog
	if m.agentCatalog != nil && len(m.agentCatalog.Agents) > 0 {
		keys := make([]string, 0, len(m.agentCatalog.Agents))
		for k := range m.agentCatalog.Agents {
			keys = append(keys, k)
		}
		sort.Strings(keys)

		for _, k := range keys {
			ag := m.agentCatalog.Agents[k]
			desc := ag.DisplayName
			if ag.AssignedModel != "" {
				desc += " (" + ag.AssignedModel + ")"
			}
			if !ag.Enabled {
				desc = "[DISABLED] " + desc
			}
			list = append(list, SuggestionItem{
				Token: "@" + ag.Identifier,
				Type:  "agent",
				Desc:  desc,
			})
		}
	}

	m.suggestions = list
}

// Update handles incoming messages and keyboard inputs.
func (m *TUIModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case turnEventMsg:
		m.handleOutboundEvent(msg.ev)
		return m, nil

	case turnDoneMsg:
		m.executing = false
		m.currentTurn = nil
		return m, nil

	case turnErrorMsg:
		m.executing = false
		m.currentTurn = nil
		m.appendRawLog("ERROR", msg.err.Error())
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    "Error: " + msg.err.Error(),
			TimeStr: time.Now().Format("15:04:05"),
		})
		return m, nil

	case autonomousReqMsg:
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    "📬 [AUTONOMOUS EVENT] " + msg.req.Prompt,
			TimeStr: time.Now().Format("15:04:05"),
		})
		m.appendRawLog("INFO", "Autonomous trigger received from "+string(msg.req.Channel))
		return m, nil

	case tea.MouseMsg:
		switch msg.Button {
		case tea.MouseButtonWheelUp:
			m.handleMouseWheel(msg.X, msg.Y, 3, true)
			return m, nil
		case tea.MouseButtonWheelDown:
			m.handleMouseWheel(msg.X, msg.Y, 3, false)
			return m, nil
		}

	case tea.KeyMsg:
		return m.handleKeyInput(msg)
	}

	return m, nil
}

// handleMouseWheel targets scrolling to the specific pane or input box under the cursor.
func (m *TUIModel) handleMouseWheel(x, y, delta int, isUp bool) {
	// If mouse is over bottom dock (input box area)
	if y > 0 && m.height > 6 && y >= m.height-6 {
		if isUp {
			if m.inputScrollOffset > 0 {
				m.inputScrollOffset--
			}
		} else {
			m.inputScrollOffset++
		}
		return
	}

	targetPane := m.activePane
	if x > 0 || y > 0 {
		leftWidth := 28
		if !m.showSidepane {
			leftWidth = 0
		} else if leftWidth > m.width/2 {
			leftWidth = m.width / 3
		}
		rightWidth := m.width - leftWidth
		centerWidth := (rightWidth * 53) / 100

		if m.showSidepane && x < leftWidth {
			targetPane = PaneDaemons
		} else if x < leftWidth+centerWidth {
			targetPane = PaneClean
		} else {
			targetPane = PaneRaw
		}
	}

	if isUp {
		m.scrollPaneUp(targetPane, delta)
	} else {
		m.scrollPaneDown(targetPane, delta)
	}
}

func (m *TUIModel) scrollPaneUp(pane, delta int) {
	switch pane {
	case PaneDaemons:
		if m.daemonScrollOffset > 0 {
			m.daemonScrollOffset -= delta
			if m.daemonScrollOffset < 0 {
				m.daemonScrollOffset = 0
			}
		}
	case PaneClean:
		m.cleanScrollOffset += delta
		if m.maxCleanScroll > 0 && m.cleanScrollOffset > m.maxCleanScroll {
			m.cleanScrollOffset = m.maxCleanScroll
		}
		m.scrollOffset = m.cleanScrollOffset
	case PaneRaw:
		m.rawScrollOffset += delta
		if m.maxRawScroll > 0 && m.rawScrollOffset > m.maxRawScroll {
			m.rawScrollOffset = m.maxRawScroll
		}
		if m.activePane == PaneRaw {
			m.scrollOffset = m.rawScrollOffset
		}
	}
}

func (m *TUIModel) scrollPaneDown(pane, delta int) {
	switch pane {
	case PaneDaemons:
		m.daemonScrollOffset += delta
		if m.maxDaemonScroll > 0 && m.daemonScrollOffset > m.maxDaemonScroll {
			m.daemonScrollOffset = m.maxDaemonScroll
		}
	case PaneClean:
		m.cleanScrollOffset -= delta
		if m.cleanScrollOffset < 0 {
			m.cleanScrollOffset = 0
		}
		m.scrollOffset = m.cleanScrollOffset
	case PaneRaw:
		m.rawScrollOffset -= delta
		if m.rawScrollOffset < 0 {
			m.rawScrollOffset = 0
		}
		if m.activePane == PaneRaw {
			m.scrollOffset = m.rawScrollOffset
		}
	}
}

func (m *TUIModel) scrollActiveUp(delta int) {
	m.scrollPaneUp(m.activePane, delta)
}

func (m *TUIModel) scrollActiveDown(delta int) {
	m.scrollPaneDown(m.activePane, delta)
}

func (m *TUIModel) scrollUp(delta int) {
	m.scrollActiveUp(delta)
}

func (m *TUIModel) scrollDown(delta int) {
	m.scrollActiveDown(delta)
}

func (m *TUIModel) scrollToTop() {
	switch m.activePane {
	case PaneDaemons:
		m.daemonScrollOffset = 0
	case PaneClean:
		m.cleanScrollOffset = m.maxCleanScroll
		m.scrollOffset = m.cleanScrollOffset
	case PaneRaw:
		m.rawScrollOffset = m.maxRawScroll
		m.scrollOffset = m.rawScrollOffset
	}
}

func (m *TUIModel) scrollToBottom() {
	switch m.activePane {
	case PaneDaemons:
		m.daemonScrollOffset = m.maxDaemonScroll
	case PaneClean:
		m.cleanScrollOffset = 0
		m.scrollOffset = 0
	case PaneRaw:
		m.rawScrollOffset = 0
		m.scrollOffset = 0
	}
}

func (m *TUIModel) syncScrollOffset() {
	switch m.activePane {
	case PaneDaemons:
		m.scrollOffset = m.daemonScrollOffset
		m.maxScroll = m.maxDaemonScroll
	case PaneClean:
		m.scrollOffset = m.cleanScrollOffset
		m.maxScroll = m.maxCleanScroll
	case PaneRaw:
		m.scrollOffset = m.rawScrollOffset
		m.maxScroll = m.maxRawScroll
	}
}

// Pane1Item represents an interactive entry in the left sidepane.
type Pane1Item struct {
	Category string // "DAEMON", "AGENT", "CMD"
	Title    string
	Action   string
	Detail   string
	Active   bool
}

func (m *TUIModel) getPane1Items() []Pane1Item {
	var items []Pane1Item
	for _, d := range m.daemons {
		items = append(items, Pane1Item{
			Category: "DAEMON",
			Title:    d.Name,
			Action:   d.Name,
			Detail:   d.State,
			Active:   d.Active,
		})
	}
	if m.agentCatalog != nil && len(m.agentCatalog.Agents) > 0 {
		keys := make([]string, 0, len(m.agentCatalog.Agents))
		for k := range m.agentCatalog.Agents {
			if k != "manager" {
				keys = append(keys, k)
			}
		}
		sort.Strings(keys)
		keys = append([]string{"manager"}, keys...)

		for _, k := range keys {
			ag := m.agentCatalog.Agents[k]
			items = append(items, Pane1Item{
				Category: "AGENT",
				Title:    "@" + ag.Identifier,
				Action:   "@" + ag.Identifier,
				Detail:   ag.DisplayName,
				Active:   ag.Enabled,
			})
		}
	}
	cmds := []struct{ k, d string }{
		{"/daemon", "Daemons"},
		{"/agents", "Catalog"},
		{"/plan", "Make DAG"},
		{"/status", "Vitals"},
		{"/clear", "Reset"},
		{"/exit", "Quit"},
	}
	for _, c := range cmds {
		items = append(items, Pane1Item{
			Category: "CMD",
			Title:    c.k,
			Action:   c.k,
			Detail:   c.d,
			Active:   true,
		})
	}
	return items
}

// handleKeyInput coordinates keyboard-first navigation and input typing.
func (m *TUIModel) handleKeyInput(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	// If suggestions popup is open, intercept navigation keys
	filtered := m.getFilteredSuggestions()
	if m.suggOpen && len(filtered) > 0 {
		switch msg.String() {
		case "up":
			if m.suggIndex > 0 {
				m.suggIndex--
			} else {
				m.suggIndex = len(filtered) - 1
			}
			m.updateSuggScroll(len(filtered))
			m.updateGhostText()
			return m, nil

		case "down":
			if m.suggIndex < len(filtered)-1 {
				m.suggIndex++
			} else {
				m.suggIndex = 0
			}
			m.updateSuggScroll(len(filtered))
			m.updateGhostText()
			return m, nil

		case "tab", "enter":
			m.acceptSuggestion(filtered[m.suggIndex])
			return m, nil

		case "esc":
			m.suggOpen = false
			m.suggScroll = 0
			m.ghostText = ""
			return m, nil
		}
	}

	// Global keyboard shortcuts
	switch msg.String() {
	case "ctrl+c":
		return m, tea.Quit

	case "tab":
		m.activePane = (m.activePane + 1) % numPanes
		if !m.showSidepane && m.activePane == PaneDaemons {
			m.activePane = (m.activePane + 1) % numPanes
		}
		m.syncScrollOffset()
		return m, nil

	case "shift+tab":
		m.activePane = (m.activePane - 1 + numPanes) % numPanes
		if !m.showSidepane && m.activePane == PaneDaemons {
			m.activePane = (m.activePane - 1 + numPanes) % numPanes
		}
		m.syncScrollOffset()
		return m, nil

	case "ctrl+d":
		m.showSidepane = !m.showSidepane
		if !m.showSidepane && m.activePane == PaneDaemons {
			m.activePane = PaneClean
		}
		m.syncScrollOffset()
		return m, nil

	case "ctrl+l":
		filters := []string{"ALL", "TOOL", "PIPE", "DEBUG"}
		m.filterIdx = (m.filterIdx + 1) % len(filters)
		m.logFilter = filters[m.filterIdx]
		return m, nil

	case "ctrl+f":
		if m.maximized == m.activePane {
			m.maximized = -1
		} else {
			m.maximized = m.activePane
		}
		return m, nil

	case "pgup":
		m.scrollActiveUp(8)
		return m, nil

	case "pgdown":
		m.scrollActiveDown(8)
		return m, nil

	case "home":
		if (m.activePane == PaneClean || m.activePane == PaneRaw) && m.input != "" {
			m.cursor = 0
			return m, nil
		}
		m.scrollToTop()
		return m, nil

	case "end":
		if (m.activePane == PaneClean || m.activePane == PaneRaw) && m.input != "" {
			m.cursor = len([]rune(m.input))
			return m, nil
		}
		m.scrollToBottom()
		return m, nil

	case "ctrl+a":
		m.cursor = 0
		return m, nil

	case "ctrl+e":
		m.cursor = len([]rune(m.input))
		return m, nil

	case "ctrl+u":
		m.input = ""
		m.cursor = 0
		m.suggOpen = false
		m.ghostText = ""
		m.historyIdx = -1
		return m, nil

	case "ctrl+w":
		runes := []rune(m.input)
		if m.cursor > 0 {
			if m.cursor > len(runes) {
				m.cursor = len(runes)
			}
			i := m.cursor
			for i > 0 && unicode.IsSpace(runes[i-1]) {
				i--
			}
			for i > 0 && !unicode.IsSpace(runes[i-1]) {
				i--
			}
			m.input = string(append(runes[:i], runes[m.cursor:]...))
			m.cursor = i
			m.computeSuggestions()
		}
		return m, nil

	case "ctrl+k":
		runes := []rune(m.input)
		if m.cursor < len(runes) {
			m.input = string(runes[:m.cursor])
			m.computeSuggestions()
		}
		return m, nil

	case "delete":
		runes := []rune(m.input)
		if m.cursor < len(runes) {
			m.input = string(append(runes[:m.cursor], runes[m.cursor+1:]...))
			m.computeSuggestions()
		}
		return m, nil

	case "ctrl+up", "alt+up", "shift+up":
		m.scrollActiveUp(2)
		return m, nil

	case "ctrl+down", "alt+down", "shift+down":
		m.scrollActiveDown(2)
		return m, nil

	case "alt+enter", "ctrl+j", "shift+enter":
		// Insert a line break (newline) into the input buffer at cursor position
		runes := []rune(m.input)
		if m.cursor > len(runes) {
			m.cursor = len(runes)
		}
		newRunes := make([]rune, 0, len(runes)+1)
		newRunes = append(newRunes, runes[:m.cursor]...)
		newRunes = append(newRunes, '\n')
		newRunes = append(newRunes, runes[m.cursor:]...)
		m.input = string(newRunes)
		m.cursor++
		m.historyIdx = -1
		return m, nil

	case "up":
		if m.activePane == PaneDaemons {
			items := m.getPane1Items()
			if len(items) > 0 {
				if m.daemonSelectedIdx > 0 {
					m.daemonSelectedIdx--
				} else {
					m.daemonSelectedIdx = len(items) - 1
				}
				if m.daemonSelectedIdx < m.daemonScrollOffset {
					m.daemonScrollOffset = m.daemonSelectedIdx
				}
			}
			return m, nil
		}
		// If actively browsing command history, continue browsing earlier history
		if m.historyIdx != -1 {
			if m.historyIdx > 0 {
				m.historyIdx--
				m.input = m.history[m.historyIdx]
				m.cursor = len([]rune(m.input))
			}
			return m, nil
		}
		// Multi-line cursor navigation: move cursor up one line if in multi-line prompt
		if m.input != "" {
			innerW := m.width - 4
			if innerW < 20 {
				innerW = 80
			}
			promptLen := 19
			firstLineWidth := max(10, innerW-promptLen)
			subseqWidth := max(10, innerW-2)
			wrapped, cursorLine, cursorOffset := m.getInputCursorPosition(firstLineWidth, subseqWidth)
			if len(wrapped) > 1 && cursorLine > 0 {
				prevLine := wrapped[cursorLine-1]
				prevRunes := []rune(prevLine.text)
				targetOffset := min(cursorOffset, len(prevRunes))
				m.cursor = prevLine.runeStart + targetOffset
				return m, nil
			}
			// Cursor is at top line of input: scroll active pane up
			m.scrollActiveUp(2)
			return m, nil
		}
		// Input is empty: recall last command from history, or scroll active pane up
		if len(m.history) > 0 {
			m.draftInput = m.input
			m.historyIdx = len(m.history) - 1
			m.input = m.history[m.historyIdx]
			m.cursor = len([]rune(m.input))
			return m, nil
		}
		m.scrollActiveUp(2)
		return m, nil

	case "down":
		if m.activePane == PaneDaemons {
			items := m.getPane1Items()
			if len(items) > 0 {
				if m.daemonSelectedIdx < len(items)-1 {
					m.daemonSelectedIdx++
				} else {
					m.daemonSelectedIdx = 0
				}
			}
			return m, nil
		}
		// If actively browsing command history, advance forward or return to draft
		if m.historyIdx != -1 {
			if m.historyIdx < len(m.history)-1 {
				m.historyIdx++
				m.input = m.history[m.historyIdx]
				m.cursor = len([]rune(m.input))
			} else {
				m.historyIdx = -1
				m.input = m.draftInput
				m.cursor = len([]rune(m.input))
			}
			return m, nil
		}
		// Multi-line cursor navigation: move cursor down one line if in multi-line prompt
		if m.input != "" {
			innerW := m.width - 4
			if innerW < 20 {
				innerW = 80
			}
			promptLen := 19
			firstLineWidth := max(10, innerW-promptLen)
			subseqWidth := max(10, innerW-2)
			wrapped, cursorLine, cursorOffset := m.getInputCursorPosition(firstLineWidth, subseqWidth)
			if len(wrapped) > 1 && cursorLine < len(wrapped)-1 {
				nextLine := wrapped[cursorLine+1]
				nextRunes := []rune(nextLine.text)
				targetOffset := min(cursorOffset, len(nextRunes))
				m.cursor = nextLine.runeStart + targetOffset
				return m, nil
			}
			// Cursor is at bottom line of input: scroll active pane down
			m.scrollActiveDown(2)
			return m, nil
		}
		m.scrollActiveDown(2)
		return m, nil

	case "enter":
		if m.activePane == PaneDaemons {
			items := m.getPane1Items()
			if len(items) > 0 && m.daemonSelectedIdx >= 0 && m.daemonSelectedIdx < len(items) {
				it := items[m.daemonSelectedIdx]
				switch it.Category {
				case "DAEMON":
					m.input = fmt.Sprintf("/daemon restart %s", it.Action)
					m.cursor = len([]rune(m.input))
					m.activePane = PaneClean
					return m, nil
				case "AGENT", "CMD":
					m.input = it.Action + " "
					m.cursor = len([]rune(m.input))
					m.activePane = PaneClean
					return m, nil
				}
			}
		}
		// If input ends with a trailing backslash '\', change line (newline) instead of submitting
		trimmed := strings.TrimRight(m.input, " \t")
		if strings.HasSuffix(trimmed, "\\") {
			runes := []rune(m.input)
			for i := len(runes) - 1; i >= 0; i-- {
				if runes[i] == '\\' {
					newRunes := append(runes[:i], '\n')
					m.input = string(newRunes)
					m.cursor = len(newRunes)
					m.historyIdx = -1
					return m, nil
				}
			}
		}
		return m.submitInput()

	case "backspace":
		runes := []rune(m.input)
		if len(runes) > 0 && m.cursor > 0 {
			if m.cursor > len(runes) {
				m.cursor = len(runes)
			}
			m.input = string(append(runes[:m.cursor-1], runes[m.cursor:]...))
			m.cursor--
			m.computeSuggestions()
		}
		return m, nil

	case "left":
		if m.cursor > 0 {
			m.cursor--
		}
		return m, nil

	case "right":
		runes := []rune(m.input)
		if m.cursor < len(runes) {
			m.cursor++
		}
		return m, nil

	case "esc":
		if m.suggOpen {
			m.suggOpen = false
			m.suggScroll = 0
			m.ghostText = ""
			return m, nil
		}
		if m.ghostText != "" {
			m.ghostText = ""
			return m, nil
		}
		if m.historyIdx != -1 {
			m.input = m.draftInput
			m.historyIdx = -1
			m.cursor = len([]rune(m.input))
			return m, nil
		}
		m.input = ""
		m.cursor = 0
		return m, nil
	}

	// Normal text entry (Rune-safe)
	if len(msg.Runes) > 0 {
		runes := []rune(m.input)
		if m.cursor > len(runes) {
			m.cursor = len(runes)
		}
		inserted := msg.Runes
		newRunes := make([]rune, 0, len(runes)+len(inserted))
		newRunes = append(newRunes, runes[:m.cursor]...)
		newRunes = append(newRunes, inserted...)
		newRunes = append(newRunes, runes[m.cursor:]...)
		m.input = string(newRunes)
		m.cursor += len(inserted)
		m.historyIdx = -1
		m.computeSuggestions()
	}

	return m, nil
}

func (m *TUIModel) getFilteredSuggestions() []SuggestionItem {
	val := strings.TrimSpace(m.input)
	if val == "" || (!strings.HasPrefix(m.input, "/") && !strings.HasPrefix(m.input, "@")) {
		return nil
	}

	query := strings.ToLower(m.input)
	var matches []SuggestionItem
	for _, item := range m.suggestions {
		if strings.HasPrefix(strings.ToLower(item.Token), query) ||
			strings.Contains(strings.ToLower(item.Token), query) ||
			strings.Contains(strings.ToLower(item.Desc), query) {
			matches = append(matches, item)
		}
	}
	return matches
}

func (m *TUIModel) updateSuggScroll(total int) {
	visibleCount := 5
	if total <= visibleCount {
		m.suggScroll = 0
		return
	}
	if m.suggIndex < m.suggScroll {
		m.suggScroll = m.suggIndex
	} else if m.suggIndex >= m.suggScroll+visibleCount {
		m.suggScroll = m.suggIndex - visibleCount + 1
	}
	if m.suggScroll+visibleCount > total {
		m.suggScroll = total - visibleCount
	}
	if m.suggScroll < 0 {
		m.suggScroll = 0
	}
}

func (m *TUIModel) computeSuggestions() {
	matches := m.getFilteredSuggestions()
	if len(matches) > 0 {
		if m.suggIndex >= len(matches) {
			m.suggIndex = 0
		}
		m.updateSuggScroll(len(matches))
		m.suggOpen = true
		m.updateGhostText()
	} else {
		m.suggOpen = false
		m.suggScroll = 0
		m.ghostText = ""
	}
}

func (m *TUIModel) updateGhostText() {
	filtered := m.getFilteredSuggestions()
	if len(filtered) > 0 && m.suggIndex < len(filtered) {
		top := filtered[m.suggIndex].Token
		topRunes := []rune(top)
		inputRunes := []rune(m.input)
		if len(topRunes) >= len(inputRunes) && strings.EqualFold(string(topRunes[:len(inputRunes)]), m.input) {
			m.ghostText = m.input + string(topRunes[len(inputRunes):])
			return
		}
	}
	m.ghostText = ""
}

func (m *TUIModel) acceptSuggestion(item SuggestionItem) {
	m.input = item.Token + " "
	m.cursor = len([]rune(m.input))
	m.suggOpen = false
	m.suggScroll = 0
	m.ghostText = ""
}

// submitInput executes slash commands or dispatches an inbound turn to the Gateway.
func (m *TUIModel) submitInput() (tea.Model, tea.Cmd) {
	prompt := strings.TrimSpace(m.input)
	m.input = ""
	m.cursor = 0
	m.suggOpen = false
	m.suggScroll = 0
	m.ghostText = ""
	m.cleanScrollOffset = 0
	m.rawScrollOffset = 0
	m.scrollOffset = 0
	m.inputScrollOffset = 0
	m.historyIdx = -1
	m.draftInput = ""

	if prompt == "" {
		return m, nil
	}

	// Append to command history if unique from previous entry
	if len(m.history) == 0 || m.history[len(m.history)-1] != prompt {
		m.history = append(m.history, prompt)
	}

	// Handle HITL approval if waiting
	if m.waitingHITL != nil {
		approved := strings.ToLower(prompt) == "y" || strings.ToLower(prompt) == "yes"
		resp := gateway.HITLResponse{
			RequestID:   m.waitingHITL.RequestID,
			SessionID:   m.sessionID,
			Approved:    approved,
			RespondedAt: time.Now().UTC(),
		}
		m.waitingHITL = nil
		_ = m.gw.RespondHITL(m.ctx, resp)
		m.appendRawLog("INFO", fmt.Sprintf("HITL response submitted: approved=%v", approved))
		return m, nil
	}

	lower := strings.ToLower(prompt)

	// Slash commands
	switch {
	case lower == "/exit" || lower == "/quit":
		return m, tea.Quit

	case lower == "/clear":
		m.cleanItems = nil
		m.rawLogs = nil
		m.appendRawLog("INFO", "Stream buffers cleared by operator")
		return m, nil

	case lower == "/session":
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    "Active Session: " + m.sessionID,
			TimeStr: time.Now().Format("15:04:05"),
		})
		return m, nil

	case lower == "/checkpoint":
		m.appendRawLog("DEBUG", "Session Governor flushing timeline WAL to SQLite disk")
		m.appendRawLog("INFO", "Checkpoint saved successfully")
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    "✔ SQLite session snapshot saved for session: " + m.sessionID,
			TimeStr: time.Now().Format("15:04:05"),
		})
		return m, nil

	case lower == "/status":
		m.handleStatusCommand()
		return m, nil

	case lower == "/daemon" || lower == "/daemon list" || lower == "/daemon status":
		m.handleDaemonListCommand()
		return m, nil

	case strings.HasPrefix(lower, "/daemon restart "):
		target := strings.TrimSpace(prompt[len("/daemon restart "):])
		m.handleDaemonRestartCommand(target)
		return m, nil

	case strings.HasPrefix(lower, "/daemon stop "):
		target := strings.TrimSpace(prompt[len("/daemon stop "):])
		m.handleDaemonStopCommand(target)
		return m, nil

	case strings.HasPrefix(lower, "/daemon start "):
		target := strings.TrimSpace(prompt[len("/daemon start "):])
		m.handleDaemonStartCommand(target)
		return m, nil

	case lower == "/agents" || lower == "/agent list":
		m.handleAgentsListCommand()
		return m, nil

	case strings.HasPrefix(lower, "/agent enable "):
		target := strings.TrimSpace(prompt[len("/agent enable "):])
		m.handleAgentToggleCommand(target, true)
		return m, nil

	case strings.HasPrefix(lower, "/agent disable "):
		target := strings.TrimSpace(prompt[len("/agent disable "):])
		m.handleAgentToggleCommand(target, false)
		return m, nil

	case lower == "/help":
		m.handleHelpCommand()
		return m, nil
	}

	// Normal turn execution
	timeStr := time.Now().Format("15:04:05")
	m.cleanItems = append(m.cleanItems, CleanEntry{
		Type:    "user",
		Text:    prompt,
		TimeStr: timeStr,
	})

	m.appendRawLog("INFO", "Inbound prompt accepted: \""+prompt+"\"")
	m.appendRawLog("PIPE", "Kernel pipe write: {\"event\":\"turn_inbound\",\"prompt\":\""+prompt+"\"}")

	// Spawn execution turn
	m.executing = true
	m.currentTurn = &CleanEntry{
		Type:    "assistant",
		TimeStr: timeStr,
	}
	m.cleanItems = append(m.cleanItems, *m.currentTurn)

	if m.gw != nil && m.program != nil {
		go func(pText string, sessID string) {
			rawReq := gateway.InboundTurnRequest{
				SessionID: sessID,
				Channel:   gateway.ClientTypeCLI,
				Trigger:   gateway.TriggerInteractive,
				Prompt:    pText,
			}
			eventCh, _, err := m.gw.SubmitTurn(m.ctx, rawReq)
			if err != nil {
				m.program.Send(turnErrorMsg{err: err})
				return
			}
			for ev := range eventCh {
				m.program.Send(turnEventMsg{ev: ev})
			}
			m.program.Send(turnDoneMsg{})
		}(prompt, m.sessionID)
	}

	return m, nil
}

// Command Handlers
func (m *TUIModel) handleDaemonListCommand() {
	m.refreshDaemons()
	timeStr := time.Now().Format("15:04:05")

	var b strings.Builder
	b.WriteString("⚙️  SYSTEM BACKGROUND DAEMONS STATUS:\n")
	b.WriteString(strings.Repeat("─", 58) + "\n")

	for _, d := range m.daemons {
		statusText := d.State
		activeText := "●"
		if !d.Active {
			activeText = "○"
		}
		b.WriteString(fmt.Sprintf("%s %-18s [%-8s] %s\n", activeText, d.Name, statusText, d.Detail))
	}
	b.WriteString(strings.Repeat("─", 58) + "\n")
	b.WriteString("Control commands: /daemon restart <name> • /daemon stop <name> • /daemon start <name>")

	m.cleanItems = append(m.cleanItems, CleanEntry{
		Type:    "system",
		Text:    b.String(),
		TimeStr: timeStr,
	})
	m.appendRawLog("INFO", fmt.Sprintf("Daemon report displayed: %d monitored daemons", len(m.daemons)))
}

func (m *TUIModel) handleDaemonRestartCommand(name string) {
	timeStr := time.Now().Format("15:04:05")
	if m.daemonProvider == nil {
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("❌ Error: Daemon provider not attached to restart daemon %q", name),
			TimeStr: timeStr,
		})
		return
	}

	m.appendRawLog("INFO", fmt.Sprintf("Restarting daemon %q...", name))
	if err := m.daemonProvider.RestartDaemon(m.ctx, name); err != nil {
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("❌ Failed to restart daemon %q: %v", name, err),
			TimeStr: timeStr,
		})
		m.appendRawLog("ERROR", fmt.Sprintf("Daemon restart %q failed: %v", name, err))
	} else {
		m.refreshDaemons()
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("✔ Daemon %q restarted successfully.", name),
			TimeStr: timeStr,
		})
		m.appendRawLog("INFO", fmt.Sprintf("Daemon %q restarted successfully", name))
	}
}

func (m *TUIModel) handleDaemonStopCommand(name string) {
	timeStr := time.Now().Format("15:04:05")
	if m.daemonProvider == nil {
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("❌ Error: Daemon provider not attached to stop daemon %q", name),
			TimeStr: timeStr,
		})
		return
	}

	if err := m.daemonProvider.StopDaemon(m.ctx, name); err != nil {
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("❌ Failed to stop daemon %q: %v", name, err),
			TimeStr: timeStr,
		})
	} else {
		m.refreshDaemons()
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("✔ Daemon %q stopped.", name),
			TimeStr: timeStr,
		})
		m.appendRawLog("INFO", fmt.Sprintf("Daemon %q stopped by operator", name))
	}
}

func (m *TUIModel) handleDaemonStartCommand(name string) {
	timeStr := time.Now().Format("15:04:05")
	if m.daemonProvider == nil {
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("❌ Error: Daemon provider not attached to start daemon %q", name),
			TimeStr: timeStr,
		})
		return
	}

	if err := m.daemonProvider.StartDaemon(m.ctx, name); err != nil {
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("❌ Failed to start daemon %q: %v", name, err),
			TimeStr: timeStr,
		})
	} else {
		m.refreshDaemons()
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("✔ Daemon %q started.", name),
			TimeStr: timeStr,
		})
		m.appendRawLog("INFO", fmt.Sprintf("Daemon %q started by operator", name))
	}
}

func (m *TUIModel) handleAgentsListCommand() {
	m.reloadAgentCatalog()
	timeStr := time.Now().Format("15:04:05")

	if m.agentCatalog == nil {
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    "❌ Agent catalog unavailable from Gateway.",
			TimeStr: timeStr,
		})
		return
	}

	var b strings.Builder
	b.WriteString(fmt.Sprintf("🤖 REGISTERED AGENT SWARM CATALOG (%d Total, %d Active):\n",
		m.agentCatalog.TotalAgents, m.agentCatalog.ActiveAgents))
	b.WriteString(strings.Repeat("─", 68) + "\n")

	keys := make([]string, 0, len(m.agentCatalog.Agents))
	for k := range m.agentCatalog.Agents {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	for _, k := range keys {
		ag := m.agentCatalog.Agents[k]
		status := "ACTIVE"
		if !ag.Enabled {
			status = "DISABLED"
		}
		coreTag := ""
		if ag.IsCore {
			coreTag = "[CORE PLANNER]"
		}
		b.WriteString(fmt.Sprintf("• @%-14s [%-8s] model:%-24s %s\n",
			ag.Identifier, status, ag.AssignedModel, coreTag))
		if len(ag.DeclaredTools) > 0 {
			b.WriteString(fmt.Sprintf("    tools (%d): %s\n", len(ag.DeclaredTools), strings.Join(ag.DeclaredTools, ", ")))
		}
	}
	b.WriteString(strings.Repeat("─", 68) + "\n")
	b.WriteString("Use '@<agent> <prompt>' to direct-address or '/agent enable|disable <id>' to toggle.")

	m.cleanItems = append(m.cleanItems, CleanEntry{
		Type:    "system",
		Text:    b.String(),
		TimeStr: timeStr,
	})
}

func (m *TUIModel) handleAgentToggleCommand(agentID string, enable bool) {
	timeStr := time.Now().Format("15:04:05")
	if m.gw == nil {
		return
	}

	err := m.gw.SetAgentStatus(agentID, enable)
	if err != nil {
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("❌ Failed to update agent %q: %v", agentID, err),
			TimeStr: timeStr,
		})
	} else {
		m.reloadAgentCatalog()
		state := "enabled"
		if !enable {
			state = "disabled"
		}
		m.cleanItems = append(m.cleanItems, CleanEntry{
			Type:    "system",
			Text:    fmt.Sprintf("✔ Agent @%s is now %s.", agentID, state),
			TimeStr: timeStr,
		})
		m.appendRawLog("INFO", fmt.Sprintf("Agent @%s status updated to enabled=%v", agentID, enable))
	}
}

func (m *TUIModel) handleStatusCommand() {
	timeStr := time.Now().Format("15:04:05")
	var mem runtime.MemStats
	runtime.ReadMemStats(&mem)

	text := fmt.Sprintf("📊 SYSTEM STATUS & VITALS:\n"+
		"• Active Session:  %s\n"+
		"• Goroutines:      %d active\n"+
		"• Memory Alloc:    %.2f MB (Sys: %.2f MB, GC pauses: %d)\n"+
		"• Gateway Hub:     Observer telemetry active\n"+
		"• Background:      %d daemons registered",
		m.sessionID,
		runtime.NumGoroutine(),
		float64(mem.Alloc)/(1024*1024),
		float64(mem.Sys)/(1024*1024),
		mem.NumGC,
		len(m.daemons),
	)

	m.cleanItems = append(m.cleanItems, CleanEntry{
		Type:    "system",
		Text:    text,
		TimeStr: timeStr,
	})
}

func (m *TUIModel) handleHelpCommand() {
	timeStr := time.Now().Format("15:04:05")
	text := "📖 KEYBOARD SHORTCUTS & COMMANDS:\n" +
		strings.Repeat("─", 60) + "\n" +
		"  [Tab]         Cycle active pane focus (Daemons → Task Stream → Logs)\n" +
		"  [Shift+Tab]   Cycle active pane focus in reverse\n" +
		"  [^D]          Toggle Left Sidepane (Show/Hide)\n" +
		"  [^L]          Cycle telemetry log filter (ALL → TOOL → PIPE → DEBUG)\n" +
		"  [^F]          Maximize/Zoom currently focused pane\n" +
		"  [PageUp/Down] Scroll history in focused stream pane\n" +
		"  [/]           Trigger command autocomplete popup\n" +
		"  [@]           Trigger agent routing autocomplete popup\n" +
		"\n" +
		"COMMANDS:\n" +
		"  /daemon [list|restart|stop|start]  Inspect and manage background watchers\n" +
		"  /agents                            List registered agents, models, and tools\n" +
		"  /agent <enable|disable> <id>       Toggle specialist agent status\n" +
		"  /plan <goal>                       Plan a task without executing tools\n" +
		"  /status                            Show runtime stats, goroutines, and memory\n" +
		"  /checkpoint                        Save SQLite turn snapshot\n" +
		"  /clear                             Clear terminal stream buffers\n" +
		"  /session                           Display active session ID\n" +
		"  /exit, /quit                       Exit assistant cleanly"

	m.cleanItems = append(m.cleanItems, CleanEntry{
		Type:    "system",
		Text:    text,
		TimeStr: timeStr,
	})
}

// handleOutboundEvent translates gateway events into clean stream updates and raw telemetry logs.
func (m *TUIModel) handleOutboundEvent(ev gateway.OutboundEvent) {
	// If agent status changed externally, update catalog
	if ev.Type == gateway.EventAgentStatusChanged {
		m.reloadAgentCatalog()
	}

	// 1. Update Raw Telemetry Stream (Pane 3)
	switch ev.Type {
	case gateway.EventToolCall:
		toolName := ""
		args := ""
		if ev.ToolCall != nil {
			toolName = ev.ToolCall.ToolName
			args = ev.ToolCall.ArgsJSON
		}
		m.appendRawLog("TOOL", fmt.Sprintf("Call: %s args=%s", toolName, args))

	case gateway.EventToolResult:
		toolName := ""
		duration := int64(0)
		output := ""
		if ev.ToolResult != nil {
			toolName = ev.ToolResult.ToolName
			duration = ev.ToolResult.DurationMs
			output = ev.ToolResult.Output
		}
		m.appendRawLog("TOOL", fmt.Sprintf("Result: %s (%dms) -> %s", toolName, duration, output))

	case gateway.EventPhaseChange:
		m.appendRawLog("DEBUG", fmt.Sprintf("Phase -> %s", ev.Phase))

	case gateway.EventSystemLog:
		if ev.Log != nil {
			m.appendRawLog(string(ev.Log.Severity), fmt.Sprintf("[%s] %s", ev.Log.Component, ev.Log.Message))
		}

	case gateway.EventSubtaskStart:
		if ev.Subtask != nil {
			m.appendRawLog("PIPE", fmt.Sprintf("Subtask START: %s (%s)", ev.Subtask.SubtaskID, ev.Subtask.Description))
		}

	case gateway.EventSubtaskComplete:
		if ev.Subtask != nil {
			m.appendRawLog("PIPE", fmt.Sprintf("Subtask DONE: %s (%dms)", ev.Subtask.SubtaskID, ev.Subtask.DurationMs))
		}

	case gateway.EventSubtaskFailed:
		if ev.Subtask != nil {
			m.appendRawLog("WARN", fmt.Sprintf("Subtask FAIL: %s: %s", ev.Subtask.SubtaskID, ev.Subtask.Error))
		}

	default:
		msg := ev.StatusMsg
		if msg == "" {
			msg = ev.TextDelta
		}
		if msg == "" && ev.Error != "" {
			msg = ev.Error
		}
		if msg != "" {
			m.appendRawLog("PIPE", fmt.Sprintf("%s: %s", ev.Type, msg))
		}
	}

	// 2. Update Clean Task Stream (Pane 2)
	idx := len(m.cleanItems) - 1
	if idx < 0 {
		return
	}

	switch ev.Type {
	case gateway.EventTokenChunk:
		m.cleanItems[idx].Text += ev.TextDelta

	case gateway.EventThoughtChunk:
		m.cleanItems[idx].Thought += ev.TextDelta

	case gateway.EventPlanCreated:
		if ev.Plan != nil {
			m.cleanItems[idx].Steps = append(m.cleanItems[idx].Steps, fmt.Sprintf("[Plan] Goal: %s (%d tasks)", ev.Plan.PrimaryGoal, len(ev.Plan.SubTasks)))
			for _, st := range ev.Plan.SubTasks {
				m.cleanItems[idx].Steps = append(m.cleanItems[idx].Steps, fmt.Sprintf("  ○ %s (%s)", st.Description, st.AssignedWorker))
			}
		}

	case gateway.EventSubtaskStart:
		if ev.Subtask != nil {
			m.cleanItems[idx].Steps = append(m.cleanItems[idx].Steps, fmt.Sprintf("[●] %s", ev.Subtask.Description))
		}

	case gateway.EventSubtaskComplete:
		if ev.Subtask != nil {
			m.cleanItems[idx].Steps = append(m.cleanItems[idx].Steps, fmt.Sprintf("[✓] %s (%dms)", ev.Subtask.Description, ev.Subtask.DurationMs))
		}

	case gateway.EventTurnComplete:
		m.cleanItems[idx].ResultPass = true
		m.cleanItems[idx].ResultText = "Turn completed successfully"

	case gateway.EventTurnError:
		m.cleanItems[idx].ResultPass = false
		m.cleanItems[idx].ResultText = "Turn failed: " + ev.Error

	case gateway.EventHITLRequest:
		if ev.HITL != nil {
			m.waitingHITL = ev.HITL
			m.cleanItems = append(m.cleanItems, CleanEntry{
				Type:    "system",
				Text:    fmt.Sprintf("⚠️ APPROVAL NEEDED: %s (Tool: %s)\nType 'y' to approve or 'n' to reject", ev.HITL.Reason, ev.HITL.ToolName),
				TimeStr: time.Now().Format("15:04:05"),
			})
		}
	}
}

func (m *TUIModel) appendRawLog(level, msg string) {
	now := time.Now().Format("15:04:05.000")
	m.rawLogs = append(m.rawLogs, RawLogEntry{
		TimeStr: now,
		Level:   level,
		Message: msg,
	})
	if len(m.rawLogs) > 300 {
		m.rawLogs = m.rawLogs[len(m.rawLogs)-300:]
	}
}

// View renders the complete terminal grid.
// View renders the complete terminal grid.
func (m *TUIModel) View() string {
	if m.width <= 0 || m.height <= 0 {
		return "Initializing terminal..."
	}

	header := m.renderHeader()
	availHeight := m.height - 1
	if availHeight < 6 {
		availHeight = 6
	}

	leftWidth := 28
	if !m.showSidepane {
		leftWidth = 0
	} else if leftWidth > m.width/2 {
		leftWidth = m.width / 3
	}

	rightWidth := m.width - leftWidth
	if rightWidth < 40 {
		rightWidth = 40
	}

	// If Pane 1 (Daemons) is maximized, display it full width above bottom dock
	if m.maximized == PaneDaemons {
		dock := m.renderBottomDock(m.width)
		dockH := lipgloss.Height(dock)
		paneH := availHeight - dockH
		if paneH < 4 {
			paneH = 4
		}
		panesRow := m.renderMaximizedPane(m.width, paneH)
		rightSection := lipgloss.JoinVertical(lipgloss.Left, panesRow, dock)
		return lipgloss.JoinVertical(lipgloss.Left, header, rightSection)
	}

	// Bottom dock placed strictly below Panes 2 & 3 (does NOT extend under Pane 1)
	bottomDock := m.renderBottomDock(rightWidth)
	dockHeight := lipgloss.Height(bottomDock)

	paneHeight := availHeight - dockHeight
	if paneHeight < 4 {
		paneHeight = 4
	}

	var rightPanes string
	if m.maximized >= 0 {
		rightPanes = m.renderMaximizedPane(rightWidth, paneHeight)
	} else {
		rightPanes = m.renderRightPanes(rightWidth, paneHeight)
	}

	rightSection := lipgloss.JoinVertical(lipgloss.Left, rightPanes, bottomDock)

	if !m.showSidepane {
		return lipgloss.JoinVertical(lipgloss.Left, header, rightSection)
	}

	// Pane 1 (Left Sidepane): Spans full height down to bottom
	leftPane := m.renderLeftPane(leftWidth, availHeight)
	body := lipgloss.JoinHorizontal(lipgloss.Top, leftPane, rightSection)

	return lipgloss.JoinVertical(lipgloss.Left, header, body)
}

func (m *TUIModel) renderHeader() string {
	focusLabel := "[2] TASK STREAM"
	switch m.activePane {
	case PaneDaemons:
		focusLabel = "[1] DAEMONS & HELP"
	case PaneRaw:
		focusLabel = "[3] RAW TELEMETRY"
	}

	left := styleHeader.Render(fmt.Sprintf(" ❯ assistant-cli • sess:%s • git:(master) ", truncate(m.sessionID, 12)))
	center := styleHeader.Render(fmt.Sprintf(" [Tab] Focus: %s ", focusLabel))
	right := styleHeader.Render(" [Go GW ●] [Py Bridge ●] [SQLite ●] ")

	space := m.width - lipgloss.Width(left) - lipgloss.Width(center) - lipgloss.Width(right)
	if space < 0 {
		space = 0
	}

	return left + strings.Repeat(" ", space/2) + center + strings.Repeat(" ", space-space/2) + right
}

// renderLeftPane renders Pane 1 (Daemons & Help) with thick border across full height.
func (m *TUIModel) renderLeftPane(w, h int) string {
	p0Border := tuiBorderDim
	if m.activePane == PaneDaemons {
		p0Border = tuiBorderActive
	}
	content := m.renderDaemonsAndHelp(w-2, h-2)
	return lipgloss.NewStyle().
		Width(w - 2).
		Height(h - 2).
		Border(lipgloss.ThickBorder()).
		BorderForeground(p0Border).
		Render(content)
}

// renderRightPanes renders Panes 2 & 3 (Task Stream & Raw Telemetry) side-by-side with thick borders.
func (m *TUIModel) renderRightPanes(width, height int) string {
	centerWidth := (width * 53) / 100
	rawWidth := width - centerWidth

	// 2. Center Pane (Task Stream)
	p1Border := tuiBorderDim
	if m.activePane == PaneClean {
		p1Border = tuiBorderActive
	}
	p1Content := m.renderTaskStream(centerWidth-2, height-2)
	p1Style := lipgloss.NewStyle().
		Width(centerWidth - 2).
		Height(height - 2).
		Border(lipgloss.ThickBorder()).
		BorderForeground(p1Border)

	// 3. Right Pane (Raw Telemetry)
	p2Border := tuiBorderDim
	if m.activePane == PaneRaw {
		p2Border = tuiBorderActive
	}
	p2Content := m.renderRawTelemetry(rawWidth-2, height-2)
	p2Style := lipgloss.NewStyle().
		Width(rawWidth - 2).
		Height(height - 2).
		Border(lipgloss.ThickBorder()).
		BorderForeground(p2Border)

	return lipgloss.JoinHorizontal(lipgloss.Top, p1Style.Render(p1Content), p2Style.Render(p2Content))
}

func (m *TUIModel) renderMaximizedPane(width, height int) string {
	w := width - 2
	h := height - 2

	var content string
	switch m.maximized {
	case PaneDaemons:
		content = m.renderDaemonsAndHelp(w, h)
	case PaneClean:
		content = m.renderTaskStream(w, h)
	case PaneRaw:
		content = m.renderRawTelemetry(w, h)
	}

	return lipgloss.NewStyle().
		Width(w).
		Height(h).
		Border(lipgloss.ThickBorder()).
		BorderForeground(tuiBorderActive).
		Render(content)
}

// Left Sidepane: Live Daemons and Live Agents Catalog
func (m *TUIModel) renderDaemonsAndHelp(w, h int) string {
	contentH := h - 3
	if contentH < 2 {
		contentH = 2
	}

	var b strings.Builder

	// 1. Live Daemons Block
	b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(tuiMuted).Render("DAEMONS"))
	b.WriteString("\n")

	daemonCount := len(m.daemons)
	for i := 0; i < daemonCount; i++ {
		d := m.daemons[i]
		dot := "● "
		dotColor := tuiDotOk
		if !d.Active {
			dotColor = tuiDotIdle
		}
		dotStyled := lipgloss.NewStyle().Foreground(dotColor).Render(dot)

		name := truncate(d.Name, w-12)
		stateStyled := lipgloss.NewStyle().Foreground(tuiMuted).Render(d.State)
		line := fmt.Sprintf("%s%-14s %s", dotStyled, name, stateStyled)

		if m.activePane == PaneDaemons && m.daemonSelectedIdx == i {
			b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FFFFFF")).Render("❯ " + line))
		} else {
			b.WriteString("  " + line)
		}
		b.WriteString("\n")
		if d.Detail != "" {
			b.WriteString(lipgloss.NewStyle().Foreground(tuiFaint).Render("    " + truncate(d.Detail, w-6)))
			b.WriteString("\n")
		}
	}

	// 2. Real Agents Catalog Block
	b.WriteString("\n")
	b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(tuiMuted).Render("AGENTS (@)"))
	b.WriteString("\n")

	agentStartIdx := daemonCount
	agentEndIdx := daemonCount
	if m.agentCatalog != nil && len(m.agentCatalog.Agents) > 0 {
		keys := make([]string, 0, len(m.agentCatalog.Agents))
		for k := range m.agentCatalog.Agents {
			if k != "manager" {
				keys = append(keys, k)
			}
		}
		sort.Strings(keys)
		keys = append([]string{"manager"}, keys...)
		agentEndIdx = agentStartIdx + len(keys)

		for i, k := range keys {
			ag := m.agentCatalog.Agents[k]
			nameStyled := lipgloss.NewStyle().Foreground(lipgloss.Color("#FFFFFF")).Render("@" + ag.Identifier)
			status := "active"
			statusColor := tuiDotOk
			if !ag.Enabled {
				status = "off"
				statusColor = tuiDotIdle
			}
			statusStyled := lipgloss.NewStyle().Foreground(statusColor).Render(status)
			itemIdx := agentStartIdx + i
			line := fmt.Sprintf("%-15s %s", nameStyled, statusStyled)
			if m.activePane == PaneDaemons && m.daemonSelectedIdx == itemIdx {
				b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FFFFFF")).Render("❯ " + line))
			} else {
				b.WriteString("  " + line)
			}
			b.WriteString("\n")
		}
	} else {
		b.WriteString(lipgloss.NewStyle().Foreground(tuiFaint).Render("  (no agents registered)\n"))
	}

	// 3. Command Cheatsheet Block
	b.WriteString("\n")
	b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(tuiMuted).Render("COMMANDS (/)"))
	b.WriteString("\n")
	cmds := []struct{ k, d string }{
		{"/daemon", "Daemons"},
		{"/agents", "Catalog"},
		{"/plan", "Make DAG"},
		{"/status", "Vitals"},
		{"/clear", "Reset"},
		{"/exit", "Quit"},
	}
	cmdStartIdx := agentEndIdx
	for i, c := range cmds {
		itemIdx := cmdStartIdx + i
		line := fmt.Sprintf("%-11s %s",
			lipgloss.NewStyle().Foreground(lipgloss.Color("#FFFFFF")).Render(c.k),
			lipgloss.NewStyle().Foreground(tuiFaint).Render(c.d),
		)
		if m.activePane == PaneDaemons && m.daemonSelectedIdx == itemIdx {
			b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FFFFFF")).Render("❯ " + line))
		} else {
			b.WriteString("  " + line)
		}
		b.WriteString("\n")
	}

	allLines := strings.Split(b.String(), "\n")
	maxScroll := max(0, len(allLines)-contentH)
	m.maxDaemonScroll = maxScroll

	offset := m.daemonScrollOffset
	if offset > maxScroll {
		offset = maxScroll
	}
	if offset < 0 {
		offset = 0
	}

	start := offset
	end := start + contentH
	if end > len(allLines) {
		end = len(allLines)
	}
	visible := allLines[start:end]
	for len(visible) < contentH {
		visible = append(visible, "")
	}

	var res strings.Builder
	// Header bar
	res.WriteString(stylePaneTitle.Render("[1] DAEMONS & HELP"))
	if maxScroll > 0 {
		pct := int((float64(offset) / float64(max(1, maxScroll))) * 100)
		res.WriteString(" ")
		res.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color("#FBBF24")).Render(fmt.Sprintf("[%d%%]", pct)))
	}
	res.WriteString("\n")
	res.WriteString(strings.Repeat("─", w))
	res.WriteString("\n")
	res.WriteString(strings.Join(visible, "\n"))
	return res.String()
}

// buildTaskStreamLines formats the clean turn stream items with rich colors and markdown styling.
func (m *TUIModel) buildTaskStreamLines(w int) []string {
	var allLines []string

	for _, it := range m.cleanItems {
		switch it.Type {
		case "user":
			userBadge := lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8")).Render("❯ OPERATOR: ")
			timeBadge := lipgloss.NewStyle().Foreground(tuiFaint).Render(it.TimeStr)
			allLines = append(allLines, userBadge+it.Text+" "+timeBadge, "")

		case "assistant":
			assistBadge := lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#A78BFA")).Render("✦ ASSISTANT (@manager):")
			allLines = append(allLines, assistBadge)

			if it.Thought != "" {
				thoughtBox := lipgloss.NewStyle().
					Border(lipgloss.ThickBorder(), false, false, false, true).
					BorderForeground(lipgloss.Color("#6366F1")).
					Foreground(lipgloss.Color("#A5B4FC")).
					Italic(true).
					Padding(0, 1).
					Render("[Thought] " + it.Thought)
				for _, tl := range strings.Split(thoughtBox, "\n") {
					allLines = append(allLines, tl)
				}
			}

			for _, step := range it.Steps {
				allLines = append(allLines, "  "+styleStepArrow.Render("➜ ")+step)
			}

			if it.Text != "" {
				mdLines := formatMarkdownLines(it.Text, w)
				allLines = append(allLines, mdLines...)
			}

			if it.ResultPass {
				allLines = append(allLines, styleSuccessTag.Render("✔ "+it.ResultText))
			}
			allLines = append(allLines, "")

		case "system":
			sysBadge := lipgloss.NewStyle().Foreground(lipgloss.Color("#94A3B8")).Render("ℹ " + it.Text)
			allLines = append(allLines, sysBadge, "")
		}
	}

	return allLines
}

// buildRawTelemetryLines formats diagnostic telemetry logs with vivid log-level colors.
func (m *TUIModel) buildRawTelemetryLines(w int) []string {
	var allRawLines []string

	for _, l := range m.rawLogs {
		if m.logFilter != "ALL" && l.Level != m.logFilter {
			continue
		}

		timeTag := lipgloss.NewStyle().Foreground(tuiFaint).Render(l.TimeStr)

		var lvlColor lipgloss.Color
		switch l.Level {
		case "INFO":
			lvlColor = lipgloss.Color("#60A5FA") // Bright blue
		case "TOOL":
			lvlColor = lipgloss.Color("#FBBF24") // Amber gold
		case "PIPE":
			lvlColor = lipgloss.Color("#A78BFA") // Violet
		case "DEBUG":
			lvlColor = lipgloss.Color("#64748B") // Muted slate
		case "WARN":
			lvlColor = lipgloss.Color("#FB923C") // Orange
		case "ERROR":
			lvlColor = lipgloss.Color("#EF4444") // Red
		default:
			lvlColor = tuiMuted
		}
		lvlTag := lipgloss.NewStyle().Bold(true).Foreground(lvlColor).Render(fmt.Sprintf("[%-5s]", l.Level))

		msg := l.Message
		// Highlights inside raw diagnostic logs
		if strings.Contains(msg, "TOKEN_CHUNK:") {
			msg = strings.Replace(msg, "TOKEN_CHUNK:", lipgloss.NewStyle().Foreground(lipgloss.Color("#C084FC")).Render("TOKEN_CHUNK:"), 1)
		} else if strings.Contains(msg, "Phase ->") {
			msg = strings.Replace(msg, "Phase ->", lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8")).Render("Phase ->"), 1)
		} else if strings.Contains(msg, "COMPLETED") {
			msg = strings.Replace(msg, "COMPLETED", lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#4ADE80")).Render("COMPLETED"), 1)
		} else if strings.Contains(msg, "check_health") {
			msg = strings.Replace(msg, "check_health", lipgloss.NewStyle().Foreground(lipgloss.Color("#FBBF24")).Render("check_health"), 1)
		}

		maxMsgLen := w - 24
		if maxMsgLen > 0 && lipgloss.Width(msg) > maxMsgLen {
			msg = truncate(msg, maxMsgLen)
		}

		allRawLines = append(allRawLines, fmt.Sprintf("%s %s %s", timeTag, lvlTag, msg))
	}

	return allRawLines
}

// Center Pane: Task Stream (Independent scrollable viewport with visual scrollbar)
func (m *TUIModel) renderTaskStream(w, h int) string {
	contentH := h - 2
	if contentH < 2 {
		contentH = 2
	}

	lines := m.buildTaskStreamLines(w - 2)
	maxScroll := max(0, len(lines)-contentH)
	m.maxCleanScroll = maxScroll

	offset := m.cleanScrollOffset
	if offset > maxScroll {
		offset = maxScroll
	}
	if offset < 0 {
		offset = 0
	}

	start := len(lines) - contentH - offset
	if start < 0 {
		start = 0
	}
	end := start + contentH
	if end > len(lines) {
		end = len(lines)
	}
	visible := lines[start:end]
	for len(visible) < contentH {
		visible = append(visible, "")
	}

	// Render scrollbar gutter on the right edge if content overflows
	if len(lines) > contentH {
		thumbH := max(1, (contentH*contentH)/len(lines))
		scrollRatio := 0.0
		if maxScroll > 0 {
			scrollRatio = float64(maxScroll-offset) / float64(maxScroll)
		}
		thumbStart := int(scrollRatio * float64(contentH-thumbH))
		for i := 0; i < contentH; i++ {
			gutter := lipgloss.NewStyle().Foreground(tuiBorderDim).Render("│")
			if i >= thumbStart && i < thumbStart+thumbH {
				gutter = lipgloss.NewStyle().Foreground(tuiBorderActive).Bold(true).Render("┃")
			}
			lineWidth := lipgloss.Width(visible[i])
			pad := (w - 2) - lineWidth
			if pad < 0 {
				pad = 0
			}
			visible[i] = visible[i] + strings.Repeat(" ", pad) + gutter
		}
	}

	var b strings.Builder
	b.WriteString(stylePaneTitle.Render("[2] TASK STREAM"))
	b.WriteString(" ")
	if offset > 0 {
		pct := int((float64(offset) / float64(max(1, maxScroll))) * 100)
		b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FBBF24")).Render(fmt.Sprintf("[↑ SCROLLED %d%% • 'End' for live]", pct)))
	} else {
		b.WriteString(stylePaneMeta.Render("(Clean Summary)"))
		b.WriteString(" ")
		b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(tuiDotOk).Render("[LIVE ●]"))
	}
	b.WriteString("\n")
	b.WriteString(strings.Repeat("─", w))
	b.WriteString("\n")
	b.WriteString(strings.Join(visible, "\n"))
	return b.String()
}

// Right Pane: Raw Telemetry Stream (Independent scrollable viewport with visual scrollbar)
func (m *TUIModel) renderRawTelemetry(w, h int) string {
	contentH := h - 2
	if contentH < 2 {
		contentH = 2
	}

	lines := m.buildRawTelemetryLines(w - 2)
	maxScroll := max(0, len(lines)-contentH)
	m.maxRawScroll = maxScroll

	offset := m.rawScrollOffset
	if offset > maxScroll {
		offset = maxScroll
	}
	if offset < 0 {
		offset = 0
	}

	start := len(lines) - contentH - offset
	if start < 0 {
		start = 0
	}
	end := start + contentH
	if end > len(lines) {
		end = len(lines)
	}
	visible := lines[start:end]
	for len(visible) < contentH {
		visible = append(visible, "")
	}

	// Render scrollbar gutter on the right edge if content overflows
	if len(lines) > contentH {
		thumbH := max(1, (contentH*contentH)/len(lines))
		scrollRatio := 0.0
		if maxScroll > 0 {
			scrollRatio = float64(maxScroll-offset) / float64(maxScroll)
		}
		thumbStart := int(scrollRatio * float64(contentH-thumbH))
		for i := 0; i < contentH; i++ {
			gutter := lipgloss.NewStyle().Foreground(tuiBorderDim).Render("│")
			if i >= thumbStart && i < thumbStart+thumbH {
				gutter = lipgloss.NewStyle().Foreground(tuiBorderActive).Bold(true).Render("┃")
			}
			lineWidth := lipgloss.Width(visible[i])
			pad := (w - 2) - lineWidth
			if pad < 0 {
				pad = 0
			}
			visible[i] = visible[i] + strings.Repeat(" ", pad) + gutter
		}
	}

	var b strings.Builder
	b.WriteString(stylePaneTitle.Render("[3] RAW TELEMETRY"))
	b.WriteString(" ")
	if offset > 0 {
		pct := int((float64(offset) / float64(max(1, maxScroll))) * 100)
		b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FBBF24")).Render(fmt.Sprintf("[↑ SCROLLED %d%% • 'End' for live]", pct)))
	} else {
		b.WriteString(stylePaneMeta.Render(fmt.Sprintf("(%s LOGS)", m.logFilter)))
		b.WriteString(" ")
		b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(tuiDotOk).Render("[LIVE ●]"))
	}
	b.WriteString("\n")
	b.WriteString(strings.Repeat("─", w))
	b.WriteString("\n")
	b.WriteString(strings.Join(visible, "\n"))
	return b.String()
}

// formatMarkdownLines renders a markdown response string with proper syntax highlighting and wrapped lines.
func formatMarkdownLines(raw string, width int) []string {
	var result []string
	rawLines := strings.Split(raw, "\n")
	inCodeBlock := false
	codeLang := ""

	for _, line := range rawLines {
		trimmed := strings.TrimSpace(line)

		// Fenced code block toggle ```
		if strings.HasPrefix(trimmed, "```") {
			if inCodeBlock {
				footer := "  └" + strings.Repeat("─", max(0, width-6))
				result = append(result, styleCodeBorder.Render(footer))
				inCodeBlock = false
				codeLang = ""
			} else {
				codeLang = strings.TrimPrefix(trimmed, "```")
				if codeLang == "" {
					codeLang = "code"
				}
				fenceHeader := fmt.Sprintf("  ┌─ [%s] ", codeLang)
				bar := strings.Repeat("─", max(0, width-lipgloss.Width(fenceHeader)-2))
				result = append(result, styleCodeBorder.Render(fenceHeader+bar))
				inCodeBlock = true
			}
			continue
		}

		if inCodeBlock {
			highlighted := highlightCodeLine(line)
			border := styleCodeBorder.Render("  │ ")
			result = append(result, border+highlighted)
			continue
		}

		if trimmed == "" {
			result = append(result, "")
			continue
		}

		// Horizontal rule
		if trimmed == "---" || trimmed == "***" || trimmed == "___" {
			result = append(result, styleFaint.Render(strings.Repeat("─", width)))
			continue
		}

		// Headings
		if strings.HasPrefix(trimmed, "# ") {
			title := strings.TrimPrefix(trimmed, "# ")
			result = append(result, styleH1.Render("■ "+title))
			continue
		}
		if strings.HasPrefix(trimmed, "## ") {
			title := strings.TrimPrefix(trimmed, "## ")
			result = append(result, styleH2.Render("◆ "+title))
			continue
		}
		if strings.HasPrefix(trimmed, "### ") {
			title := strings.TrimPrefix(trimmed, "### ")
			result = append(result, styleH3.Render("● "+title))
			continue
		}
		if strings.HasPrefix(trimmed, "#### ") {
			title := strings.TrimPrefix(trimmed, "#### ")
			result = append(result, styleH4.Render("▸ "+title))
			continue
		}

		// Turn result checkmark
		if strings.HasPrefix(trimmed, "✔ ") || strings.Contains(trimmed, "Turn completed successfully") {
			result = append(result, styleSuccessTag.Render(trimmed))
			continue
		}

		// Bullet lists
		indent := len(line) - len(strings.TrimLeft(line, " "))
		if strings.HasPrefix(trimmed, "* ") || strings.HasPrefix(trimmed, "- ") {
			content := strings.TrimSpace(trimmed[2:])
			bulletLines := formatBulletLine(indent, content, width)
			result = append(result, bulletLines...)
			continue
		}

		// Numbered lists e.g. "1. ..."
		if isNumberedList(trimmed) {
			dotIdx := strings.Index(trimmed, ".")
			num := trimmed[:dotIdx+1]
			content := strings.TrimSpace(trimmed[dotIdx+1:])
			styledNum := styleNumBadge.Render("  " + num + " ")
			formattedContent := formatInlineMarkdown(content)
			wrapped := wrapTextWithIndent(styledNum+formattedContent, len(num)+3, width)
			result = append(result, wrapped...)
			continue
		}

		// Regular text line
		formatted := formatInlineMarkdown(trimmed)
		wrapped := wrapTextWithIndent(formatted, 0, width)
		result = append(result, wrapped...)
	}

	return result
}

func formatBulletLine(indent int, content string, width int) []string {
	var bulletPrefix string
	if indent >= 4 {
		bulletPrefix = "      ▪ "
	} else if indent >= 2 {
		bulletPrefix = "    ◦ "
	} else {
		bulletPrefix = "  • "
	}

	styledPrefix := styleBulletMain.Render(bulletPrefix)
	if indent >= 2 {
		styledPrefix = styleBulletSub.Render(bulletPrefix)
	}

	trimmed := strings.TrimSpace(content)
	// Check if bullet starts with bold key: **Key**:
	if strings.HasPrefix(trimmed, "**") {
		endBold := strings.Index(trimmed[2:], "**")
		if endBold != -1 {
			key := trimmed[2 : 2+endBold]
			rest := trimmed[2+endBold+2:]
			if strings.HasPrefix(rest, ":") {
				rest = strings.TrimPrefix(rest, ":")
				rest = strings.TrimPrefix(rest, " ")
				renderedKey := styleKeyLabel.Render(key + ":")
				formattedRest := formatInlineMarkdown(rest)
				fullFirstLine := styledPrefix + renderedKey + " " + formattedRest
				return wrapTextWithIndent(fullFirstLine, len(bulletPrefix)+len(key)+2, width)
			}
		}
	}

	formattedContent := formatInlineMarkdown(trimmed)
	return wrapTextWithIndent(styledPrefix+formattedContent, len(bulletPrefix), width)
}

func formatInlineMarkdown(text string) string {
	// 1. Process inline code `...`
	if strings.Contains(text, "`") {
		var b strings.Builder
		inCode := false
		start := 0
		for i := 0; i < len(text); i++ {
			if text[i] == '`' {
				if inCode {
					code := text[start:i]
					b.WriteString(styleCodeSpan.Render(code))
					inCode = false
					start = i + 1
				} else {
					b.WriteString(text[start:i])
					inCode = true
					start = i + 1
				}
			}
		}
		if start < len(text) {
			if inCode {
				b.WriteString("`" + text[start:])
			} else {
				b.WriteString(text[start:])
			}
		}
		text = b.String()
	}

	// 2. Process bold **...**
	if strings.Contains(text, "**") {
		var b strings.Builder
		inBold := false
		start := 0
		for i := 0; i < len(text)-1; i++ {
			if text[i] == '*' && text[i+1] == '*' {
				if inBold {
					boldText := text[start:i]
					b.WriteString(styleBoldText.Render(boldText))
					inBold = false
					i++
					start = i + 1
				} else {
					b.WriteString(text[start:i])
					inBold = true
					i++
					start = i + 1
				}
			}
		}
		if start < len(text) {
			b.WriteString(text[start:])
		}
		text = b.String()
	}

	return text
}

func wrapTextWithIndent(text string, indentLen int, width int) []string {
	if width < 20 {
		width = 20
	}
	if lipgloss.Width(text) <= width {
		return []string{text}
	}

	words := strings.Fields(text)
	if len(words) == 0 {
		return []string{text}
	}

	var lines []string
	var curLine strings.Builder
	indentStr := strings.Repeat(" ", indentLen)

	for _, w := range words {
		wWidth := lipgloss.Width(w)
		curWidth := lipgloss.Width(curLine.String())
		if curWidth == 0 {
			curLine.WriteString(w)
		} else if curWidth+1+wWidth <= width {
			curLine.WriteString(" " + w)
		} else {
			lines = append(lines, curLine.String())
			curLine.Reset()
			curLine.WriteString(indentStr + w)
		}
	}
	if curLine.Len() > 0 {
		lines = append(lines, curLine.String())
	}
	return lines
}

func isNumberedList(s string) bool {
	dotIdx := strings.Index(s, ".")
	if dotIdx <= 0 || dotIdx > 3 {
		return false
	}
	numStr := s[:dotIdx]
	for _, r := range numStr {
		if r < '0' || r > '9' {
			return false
		}
	}
	if len(s) > dotIdx+1 && s[dotIdx+1] == ' ' {
		return true
	}
	return false
}

func highlightCodeLine(line string) string {
	trimmed := strings.TrimSpace(line)
	if strings.HasPrefix(trimmed, "//") || strings.HasPrefix(trimmed, "#") {
		return lipgloss.NewStyle().Foreground(lipgloss.Color("#64748B")).Render(line)
	}

	keywords := []string{"func", "return", "package", "import", "type", "struct", "if", "else", "for", "range", "def", "class", "const", "let", "var"}
	words := strings.Split(line, " ")
	for i, w := range words {
		cleaned := strings.Trim(w, "(),:{};")
		for _, kw := range keywords {
			if cleaned == kw {
				words[i] = strings.Replace(w, cleaned, lipgloss.NewStyle().Foreground(lipgloss.Color("#C084FC")).Bold(true).Render(cleaned), 1)
				break
			}
		}
	}
	return strings.Join(words, " ")
}

// renderBottomDock positions the suggestions popup, dynamic input box, and status line.
func (m *TUIModel) renderBottomDock(width int) string {
	var b strings.Builder

	// 1. Scrollable suggestions popup (if open)
	if sugg := m.renderSuggestionsPopup(width); sugg != "" {
		b.WriteString(sugg)
	}

	// 2. Dynamic auto-growing input box with thick border
	b.WriteString(m.renderInputBox(width))
	b.WriteString("\n")

	// 3. Status bar with shortcuts and system telemetry
	shortcuts := lipgloss.NewStyle().Foreground(tuiFaint).Render(
		"[Tab] Focus • [PgUp/Dn/Wheel] Scroll Pane • [/] Cmds • [@] Agents • [^L] Logs • [^D] Sidepane • [^F] Zoom • [^C] Exit",
	)
	vitals := lipgloss.NewStyle().Foreground(tuiMuted).Render(
		fmt.Sprintf("Goroutines: %d • Daemons: %d", runtime.NumGoroutine(), len(m.daemons)),
	)

	space := width - lipgloss.Width(shortcuts) - lipgloss.Width(vitals)
	if space < 0 {
		space = 0
	}
	b.WriteString(shortcuts + strings.Repeat(" ", space) + vitals)

	return b.String()
}

// renderSuggestionsPopup displays scrollable agent and command suggestions with thick borders.
func (m *TUIModel) renderSuggestionsPopup(width int) string {
	filtered := m.getFilteredSuggestions()
	if !m.suggOpen || len(filtered) == 0 {
		return ""
	}
	m.updateSuggScroll(len(filtered))
	visibleCount := 5
	if len(filtered) < visibleCount {
		visibleCount = len(filtered)
	}
	startIdx := m.suggScroll
	endIdx := startIdx + visibleCount
	if endIdx > len(filtered) {
		endIdx = len(filtered)
	}

	var b strings.Builder
	headerText := fmt.Sprintf("SUGGESTIONS (%d/%d • [↑]/[↓] scroll • [Tab] complete)", m.suggIndex+1, len(filtered))
	b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(tuiMuted).Render(headerText))
	b.WriteString("\n")

	for i := startIdx; i < endIdx; i++ {
		s := filtered[i]
		tag := lipgloss.NewStyle().Foreground(tuiFaint).Render("[" + strings.ToUpper(s.Type) + "]")
		maxDescLen := width - 32
		if maxDescLen < 10 {
			maxDescLen = 10
		}
		line := fmt.Sprintf("%-6s %-16s %s", tag, s.Token, truncate(s.Desc, maxDescLen))
		if i == m.suggIndex {
			b.WriteString(styleSuggSelected.Render("❯ " + line))
		} else {
			b.WriteString(styleSuggRow.Render("  " + line))
		}
		if i < endIdx-1 {
			b.WriteString("\n")
		}
	}

	return lipgloss.NewStyle().
		Width(width - 2).
		Border(lipgloss.ThickBorder()).
		BorderForeground(tuiBorderDim).
		Padding(0, 1).
		Render(b.String()) + "\n"
}

// wrappedInputLine stores tokenized line chunks with rune boundaries.
type wrappedInputLine struct {
	text      string
	runeStart int
	runeEnd   int
}

// wrapInputToLines parses input into lines respecting both hard newlines (\n)
// and soft wrapping at word boundaries.
func wrapInputToLines(input string, firstLineWidth, subseqWidth int) []wrappedInputLine {
	runes := []rune(input)
	if len(runes) == 0 {
		return []wrappedInputLine{{text: "", runeStart: 0, runeEnd: 0}}
	}

	var lines []wrappedInputLine
	rawStart := 0
	lineLimit := firstLineWidth

	for rawStart <= len(runes) {
		nextNL := -1
		for i := rawStart; i < len(runes); i++ {
			if runes[i] == '\n' {
				nextNL = i
				break
			}
		}

		paragraphEnd := len(runes)
		if nextNL != -1 {
			paragraphEnd = nextNL
		}
		paragraphRunes := runes[rawStart:paragraphEnd]

		if len(paragraphRunes) == 0 {
			lines = append(lines, wrappedInputLine{
				text:      "",
				runeStart: rawStart,
				runeEnd:   paragraphEnd,
			})
		} else {
			pStart := 0
			for pStart < len(paragraphRunes) {
				remLen := len(paragraphRunes) - pStart
				if remLen <= lineLimit {
					lines = append(lines, wrappedInputLine{
						text:      string(paragraphRunes[pStart:]),
						runeStart: rawStart + pStart,
						runeEnd:   rawStart + len(paragraphRunes),
					})
					break
				}

				breakAt := -1
				for i := pStart + lineLimit; i > pStart; i-- {
					if unicode.IsSpace(paragraphRunes[i]) {
						breakAt = i
						break
					}
				}

				if breakAt > pStart {
					lines = append(lines, wrappedInputLine{
						text:      string(paragraphRunes[pStart:breakAt]),
						runeStart: rawStart + pStart,
						runeEnd:   rawStart + breakAt,
					})
					pStart = breakAt + 1
				} else {
					lines = append(lines, wrappedInputLine{
						text:      string(paragraphRunes[pStart : pStart+lineLimit]),
						runeStart: rawStart + pStart,
						runeEnd:   rawStart + pStart + lineLimit,
					})
					pStart += lineLimit
				}
				lineLimit = subseqWidth
			}
		}

		if nextNL == -1 {
			break
		}
		rawStart = nextNL + 1
		lineLimit = subseqWidth
	}

	return lines
}

// getInputCursorPosition returns the wrapped lines and the (line, col) where cursor lands.
func (m *TUIModel) getInputCursorPosition(firstLineWidth, subseqWidth int) (wrapped []wrappedInputLine, cursorLine, cursorOffset int) {
	wrapped = wrapInputToLines(m.input, firstLineWidth, subseqWidth)
	if len(wrapped) == 0 {
		return []wrappedInputLine{{text: "", runeStart: 0, runeEnd: 0}}, 0, 0
	}

	runes := []rune(m.input)
	cursor := m.cursor
	if cursor < 0 {
		cursor = 0
	}
	if cursor > len(runes) {
		cursor = len(runes)
	}

	for i, l := range wrapped {
		if cursor >= l.runeStart && cursor <= l.runeEnd {
			cursorLine = i
			cursorOffset = cursor - l.runeStart
			break
		}
	}
	if cursor == len(runes) && len(wrapped) > 0 {
		cursorLine = len(wrapped) - 1
		cursorOffset = cursor - wrapped[cursorLine].runeStart
	}
	return wrapped, cursorLine, cursorOffset
}

// renderInputBox dynamically wraps lines at word boundaries with a visible block cursor
// and internal scrolling for long prompts.
func (m *TUIModel) renderInputBox(width int) string {
	promptLabel := stylePromptLabel.Render("assistant:master ❯ ")
	if m.waitingHITL != nil {
		promptLabel = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#EAB308")).Render("APPROVAL (y/n) ❯ ")
	}

	innerW := width - 4 // border 2 + padding 2
	if innerW < 20 {
		innerW = 20
	}

	promptLen := lipgloss.Width(promptLabel)
	firstLineWidth := innerW - promptLen
	if firstLineWidth < 10 {
		firstLineWidth = 10
	}
	subseqWidth := innerW - 2
	if subseqWidth < 10 {
		subseqWidth = 10
	}

	runes := []rune(m.input)
	cursor := m.cursor
	if cursor < 0 {
		cursor = 0
	}
	if cursor > len(runes) {
		cursor = len(runes)
	}

	ghostPart := ""
	if m.ghostText != "" && len(m.ghostText) > len(m.input) {
		topRunes := []rune(m.ghostText)
		if len(topRunes) > len(runes) {
			ghostPart = string(topRunes[len(runes):])
		}
	}

	styleCursor := lipgloss.NewStyle().
		Background(lipgloss.Color("#FFFFFF")).
		Foreground(lipgloss.Color("#000000")).
		Bold(true)

	wrapped, cursorLine, cursorOffset := m.getInputCursorPosition(firstLineWidth, subseqWidth)

	var renderedLines []string
	for i, l := range wrapped {
		lineRunes := []rune(l.text)
		var lineContent string

		if i == cursorLine {
			if cursorOffset < len(lineRunes) {
				before := string(lineRunes[:cursorOffset])
				curChar := styleCursor.Render(string(lineRunes[cursorOffset]))
				after := string(lineRunes[cursorOffset+1:])
				lineContent = before + curChar + after
			} else {
				curChar := styleCursor.Render(" ")
				after := ""
				if ghostPart != "" && i == len(wrapped)-1 {
					after = styleGhost.Render(ghostPart)
				}
				lineContent = l.text + curChar + after
			}
		} else {
			lineContent = l.text
		}

		if i == 0 {
			renderedLines = append(renderedLines, promptLabel+lineContent)
		} else {
			renderedLines = append(renderedLines, "  "+lineContent)
		}
	}

	// Cap display height at 4 visible lines; internally scroll so cursor line is always visible
	maxVisible := 4
	visibleLines := renderedLines
	if len(renderedLines) > maxVisible {
		startLine := 0
		if cursorLine >= maxVisible {
			startLine = cursorLine - maxVisible + 1
		}
		// Allow manual scroll adjustment within bounds
		if m.inputScrollOffset > 0 {
			startLine = m.inputScrollOffset
		}
		if cursorLine < startLine {
			startLine = cursorLine
		} else if cursorLine >= startLine+maxVisible {
			startLine = cursorLine - maxVisible + 1
		}
		endLine := startLine + maxVisible
		if endLine > len(renderedLines) {
			endLine = len(renderedLines)
			startLine = max(0, endLine-maxVisible)
		}
		visibleLines = renderedLines[startLine:endLine]
		m.inputScrollOffset = startLine
	} else {
		m.inputScrollOffset = 0
	}

	inputBorder := tuiBorderDim
	if m.input != "" || m.waitingHITL != nil {
		inputBorder = tuiBorderActive
	}

	return lipgloss.NewStyle().
		Width(width - 2).
		Border(lipgloss.ThickBorder()).
		BorderForeground(inputBorder).
		Padding(0, 1).
		Render(strings.Join(visibleLines, "\n"))
}

func truncate(str string, maxLen int) string {
	if maxLen <= 0 {
		return ""
	}
	if len(str) <= maxLen {
		return str
	}
	return str[:maxLen-1] + "…"
}

// TUI provides the runner entry point for the Bubble Tea terminal interface.
type TUI struct {
	gw             *gateway.Gateway
	sessionID      string
	daemonProvider DaemonProvider
}

// NewTUI creates a new TUI runner instance.
func NewTUI(gw *gateway.Gateway, sessionID string) *TUI {
	return &TUI{
		gw:        gw,
		sessionID: sessionID,
	}
}

// SetDaemonProvider binds the daemon supervisor controller to the TUI.
func (t *TUI) SetDaemonProvider(dp DaemonProvider) {
	t.daemonProvider = dp
}

// Run executes the Bubble Tea program with full alt-screen buffer and context cancellation.
func (t *TUI) Run(ctx context.Context) error {
	m := NewTUIModel(t.gw, t.sessionID, t.daemonProvider, ctx)

	p := tea.NewProgram(
		m,
		tea.WithContext(ctx),
		tea.WithAltScreen(),
		tea.WithMouseCellMotion(),
	)
	m.SetProgram(p)

	// Register autonomous consumer to stream background watcher events into the TUI
	if t.gw != nil {
		t.gw.RegisterAutonomousConsumer(t.sessionID, func(req gateway.InboundTurnRequest, eventCh <-chan gateway.OutboundEvent) {
			p.Send(autonomousReqMsg{req: req})
			for ev := range eventCh {
				p.Send(turnEventMsg{ev: ev})
			}
		})
		defer t.gw.UnregisterAutonomousConsumer(t.sessionID)
	}

	_, err := p.Run()
	return err
}

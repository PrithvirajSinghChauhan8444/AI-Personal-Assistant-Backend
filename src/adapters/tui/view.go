package tui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/mattn/go-runewidth"
)

var (
	styleHeader = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#FAFAFA")).
			Background(lipgloss.Color("#4C1D95")).
			Padding(0, 1)

	stylePane = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("#4B5563"))

	stylePaneActive = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("#7C3AED"))

	styleSuggestBox = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder()).
			BorderForeground(lipgloss.Color("#3B82F6")).
			Background(lipgloss.Color("#111827")).
			Padding(0, 1)

	styleSuggestSelected = lipgloss.NewStyle().
				Bold(true).
				Foreground(lipgloss.Color("#60A5FA")).
				Background(lipgloss.Color("#1E3A8A"))

	styleFooter = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#9CA3AF")).
			Background(lipgloss.Color("#1F2937")).
			Padding(0, 1)

	styleLogTime = lipgloss.NewStyle().Foreground(lipgloss.Color("#6B7280"))
	styleLogTag  = lipgloss.NewStyle().Foreground(lipgloss.Color("#F59E0B")).Bold(true)
	styleLogErr  = lipgloss.NewStyle().Foreground(lipgloss.Color("#EF4444")).Bold(true)
	styleUserTag = lipgloss.NewStyle().Foreground(lipgloss.Color("#10B981")).Bold(true)
	styleAsstTag = lipgloss.NewStyle().Foreground(lipgloss.Color("#8B5CF6")).Bold(true)
)

// ViewResult contains the rendered ANSI string and hardware cursor coordinates.
type ViewResult struct {
	Screen    string
	CursorRow int
	CursorCol int
}

// RenderScreen generates the complete screen frame and returns the active cursor coordinates.
func RenderScreen(s *UIState) ViewResult {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.Width < 80 || s.Height < 24 {
		return ViewResult{
			Screen:    renderTerminalTooSmall(s.Width, s.Height),
			CursorRow: 1,
			CursorCol: 1,
		}
	}

	header := renderHeader(s)
	footer := renderFooter(s)
	inputBox, inputHeight, relCursorRow, relCursorCol := renderInputBox(s)

	suggestHeight := 0
	suggestStr := ""
	if s.IsSuggestVisible && len(s.Suggestions) > 0 {
		suggestStr = renderSuggestions(s)
		suggestHeight = lipgloss.Height(suggestStr)
	}

	occupiedHeight := lipgloss.Height(header) + lipgloss.Height(footer) + inputHeight + suggestHeight
	mainHeight := s.Height - occupiedHeight
	if mainHeight < 6 {
		mainHeight = 6
	}

	panes := renderMainPanes(s, mainHeight)

	var sb strings.Builder
	sb.WriteString(header + "\n")
	sb.WriteString(panes + "\n")
	if suggestStr != "" {
		sb.WriteString(suggestStr + "\n")
	}
	sb.WriteString(inputBox + "\n")
	sb.WriteString(footer)

	// Calculate absolute hardware cursor position
	cursorRow := lipgloss.Height(header) + lipgloss.Height(panes) + suggestHeight + relCursorRow
	cursorCol := relCursorCol

	return ViewResult{
		Screen:    sb.String(),
		CursorRow: cursorRow,
		CursorCol: cursorCol,
	}
}

func renderHeader(s *UIState) string {
	sessShort := s.SessionID
	if len(sessShort) > 8 {
		sessShort = sessShort[:8]
	}
	left := fmt.Sprintf(" Assistant TUI | Session: %s | Target: @%s | Model: %s",
		sessShort, s.ActiveAgent, s.AssignedModel)
	if s.IsGenerating {
		left += " [Thinking/Streaming...]"
	}
	return styleHeader.Width(s.Width).Render(left)
}

func renderFooter(s *UIState) string {
	hints := " [Tab] Accept  [Ctrl+L] Toggle Logs  [PgUp/PgDn] Scroll  [Ctrl+C] Cancel  [?] Help"
	return styleFooter.Width(s.Width).Render(hints)
}

func renderMainPanes(s *UIState, height int) string {
	if !s.ShowLogsPane || s.Width < 100 {
		respWidth := s.Width - 2
		lines := prepareResponseLines(s)
		content := sliceLinesToHeight(lines, height-2, s.ResponseScroll)
		return stylePaneActive.Width(respWidth).Height(height).Render(content)
	}

	respWidth := (s.Width * 62 / 100) - 2
	logsWidth := s.Width - respWidth - 5

	respLines := prepareResponseLines(s)
	respContent := sliceLinesToHeight(respLines, height-2, s.ResponseScroll)

	logsLines := prepareLogLines(s.Logs, logsWidth)
	logsContent := sliceLinesToHeight(logsLines, height-2, s.LogsScroll)

	left := stylePaneActive.Width(respWidth).Height(height).Render(respContent)
	right := stylePane.Width(logsWidth).Height(height).Render(logsContent)

	return lipgloss.JoinHorizontal(lipgloss.Top, left, " ", right)
}

func prepareResponseLines(s *UIState) []string {
	var lines []string
	for _, l := range s.ConversationLines {
		if strings.HasPrefix(l, "User: ") {
			lines = append(lines, styleUserTag.Render("User: ")+l[6:])
		} else if strings.HasPrefix(l, "Assistant: ") {
			lines = append(lines, styleAsstTag.Render("Assistant: ")+l[11:])
		} else {
			lines = append(lines, l)
		}
	}
	active := s.ActiveResponse.String()
	if active != "" {
		for i, line := range strings.Split(active, "\n") {
			if i == 0 && len(lines) > 0 && !strings.Contains(lines[len(lines)-1], "Assistant: ") {
				lines = append(lines, styleAsstTag.Render("Assistant: ")+line)
			} else {
				lines = append(lines, line)
			}
		}
	}
	if len(lines) == 0 {
		lines = append(lines, lipgloss.NewStyle().Foreground(lipgloss.Color("#6B7280")).Render("Awaiting input... Type your prompt below."))
	}
	return lines
}

func prepareLogLines(entries []LogEntry, width int) []string {
	var lines []string
	if len(entries) == 0 {
		return []string{lipgloss.NewStyle().Foreground(lipgloss.Color("#6B7280")).Render("No telemetry events yet.")}
	}
	for _, e := range entries {
		t := styleLogTime.Render(e.Timestamp.Format("15:04:05"))
		tag := styleLogTag.Render("[" + e.Category + "]")
		if e.IsError {
			tag = styleLogErr.Render("[" + e.Category + "]")
		}
		raw := fmt.Sprintf("%s %s %s", t, tag, e.Message)
		lines = append(lines, runewidth.Truncate(raw, width, "..."))
	}
	return lines
}

func sliceLinesToHeight(lines []string, height, scroll int) string {
	if height <= 0 {
		return ""
	}
	total := len(lines)
	if total == 0 {
		return ""
	}

	end := total - scroll
	if end > total {
		end = total
	}
	if end < 1 {
		end = 1
	}

	start := end - height
	if start < 0 {
		start = 0
	}

	return strings.Join(lines[start:end], "\n")
}

func renderSuggestions(s *UIState) string {
	maxShow := minInt(len(s.Suggestions), 5)
	var rows []string
	for i := 0; i < maxShow; i++ {
		item := s.Suggestions[i]
		line := fmt.Sprintf("%-12s  %s", item.Token, item.Description)
		if i == s.SelectedSuggest {
			rows = append(rows, styleSuggestSelected.Render("> "+line))
		} else {
			rows = append(rows, "  "+line)
		}
	}
	return styleSuggestBox.Width(s.Width - 4).Render(strings.Join(rows, "\n"))
}

func renderInputBox(s *UIState) (boxStr string, height int, relRow int, relCol int) {
	promptPrefix := "> "
	prefixWidth := runewidth.StringWidth(promptPrefix)

	// Auto-wrapping within terminal width
	contentWidth := s.Width - 4
	if contentWidth < 20 {
		contentWidth = 20
	}

	lines := wrapRunes(s.InputBuffer, contentWidth-prefixWidth)
	if len(lines) == 0 {
		lines = []string{""}
	}

	var sb strings.Builder
	for i, l := range lines {
		if i == 0 {
			sb.WriteString(promptPrefix + l)
		} else {
			sb.WriteString(strings.Repeat(" ", prefixWidth) + l)
		}
		if i < len(lines)-1 {
			sb.WriteString("\n")
		}
	}

	renderedBox := lipgloss.NewStyle().
		Border(lipgloss.NormalBorder(), true, false, false, false).
		BorderForeground(lipgloss.Color("#6B7280")).
		Width(s.Width).
		Render(sb.String())

	// Compute relative cursor row & col
	cursorLine, cursorCol := computeCursorOffset(s.InputBuffer, s.CursorPos, contentWidth-prefixWidth)
	relRow = cursorLine + 1 // Account for top border
	relCol = prefixWidth + cursorCol + 1

	return renderedBox, lipgloss.Height(renderedBox), relRow, relCol
}

func wrapRunes(input []rune, maxCols int) []string {
	if len(input) == 0 {
		return []string{""}
	}
	if maxCols <= 0 {
		maxCols = 40
	}

	var lines []string
	var current strings.Builder
	curWidth := 0

	for _, r := range input {
		if r == '\n' {
			lines = append(lines, current.String())
			current.Reset()
			curWidth = 0
			continue
		}
		rw := runewidth.RuneWidth(r)
		if curWidth+rw > maxCols {
			lines = append(lines, current.String())
			current.Reset()
			curWidth = 0
		}
		current.WriteRune(r)
		curWidth += rw
	}
	lines = append(lines, current.String())
	return lines
}

func computeCursorOffset(input []rune, pos, maxCols int) (int, int) {
	if pos > len(input) {
		pos = len(input)
	}
	if maxCols <= 0 {
		maxCols = 40
	}

	line := 0
	col := 0
	for i := 0; i < pos; i++ {
		r := input[i]
		if r == '\n' {
			line++
			col = 0
			continue
		}
		rw := runewidth.RuneWidth(r)
		if col+rw > maxCols {
			line++
			col = 0
		}
		col += rw
	}
	return line, col
}

func renderTerminalTooSmall(w, h int) string {
	return fmt.Sprintf("Terminal resolution (%dx%d) is below the minimum required (80x24).\nPlease resize your terminal window.", w, h)
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

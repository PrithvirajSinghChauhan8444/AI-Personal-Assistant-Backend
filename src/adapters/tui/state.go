package tui

import (
	"strings"
	"sync"
	"time"
)

// UIState is the central synchronized state for the TUI adapter.
type UIState struct {
	mu sync.Mutex

	// Dimensions
	Width  int
	Height int

	// View Controls
	ShowLogsPane bool

	// Conversation Viewport
	ConversationLines []string
	ActiveResponse    strings.Builder
	ResponseScroll    int
	IsGenerating      bool

	// Telemetry & Logs
	Logs       []LogEntry
	LogsScroll int

	// Input Bar & Editing
	InputBuffer  []rune
	CursorPos    int
	History      []string
	HistoryIndex int

	// Auto-Suggestion Popup
	Suggestions      []SuggestionItem
	SelectedSuggest  int
	IsSuggestVisible bool
	ActiveWordStart  int
	ActivePrefix     string

	// Status & Metadata
	SessionID     string
	ActiveAgent   string
	AssignedModel string
	StatusMessage string
	ErrorMessage  string
	LastActivity  time.Time
}

// NewUIState initializes default state values.
func NewUIState(sessionID string) *UIState {
	return &UIState{
		Width:             100,
		Height:            30,
		ShowLogsPane:      true,
		ConversationLines: []string{"Welcome to Assistant TUI. Type a prompt, '/' for commands, or '@' for agents."},
		History:           []string{},
		HistoryIndex:      -1,
		SessionID:         sessionID,
		ActiveAgent:       "manager",
		AssignedModel:     "gemini-2.5-flash",
		LastActivity:      time.Now(),
	}
}

// AppendLog adds an operational telemetry log entry (thread-safe).
func (s *UIState) AppendLog(category, message string, isError bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.appendLogLocked(category, message, isError)
}

func (s *UIState) appendLogLocked(category, message string, isError bool) {
	entry := LogEntry{
		Timestamp: time.Now(),
		Category:  category,
		Message:   message,
		IsError:   isError,
	}
	s.Logs = append(s.Logs, entry)
	if len(s.Logs) > 300 {
		s.Logs = s.Logs[len(s.Logs)-300:]
	}
	s.LastActivity = time.Now()
}

// ResetInput clears the input prompt after submission.
func (s *UIState) ResetInput() {
	if len(s.InputBuffer) > 0 {
		text := string(s.InputBuffer)
		s.History = append(s.History, text)
	}
	s.InputBuffer = nil
	s.CursorPos = 0
	s.HistoryIndex = -1
	s.IsSuggestVisible = false
	s.Suggestions = nil
}

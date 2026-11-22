package tui

import (
	"time"

	"assistant/src/adapters/cli"
)

// SuggestionKind distinguishes command types from agent targets.
type SuggestionKind string

const (
	KindSlashCommand SuggestionKind = "COMMAND"
	KindAgentMention SuggestionKind = "AGENT"
)

// SuggestionItem defines an autocomplete entry shown in the suggestion dropdown.
type SuggestionItem struct {
	Token       string         `json:"token"`       // e.g. "/switch", "@browser"
	Title       string         `json:"title"`       // Display name
	Description string         `json:"description"` // Contextual summary
	Kind        SuggestionKind `json:"kind"`
}

// LogEntry encapsulates timestamped operational metadata and tool traces.
type LogEntry struct {
	Timestamp time.Time `json:"timestamp"`
	Category  string    `json:"category"` // "TOOL-CALL", "TOOL-OK", "THOUGHT", "PLAN", "STATUS", "ERROR"
	Message   string    `json:"message"`
	IsError   bool      `json:"is_error"`
}

// DaemonProvider exposes lifecycle operations and health inspection for background daemons.
type DaemonProvider = cli.DaemonProvider

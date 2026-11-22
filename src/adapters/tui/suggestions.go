package tui

import (
	"sort"
	"strings"
	"unicode"
)

// SuggestionEngine provides type-ahead matching for slash commands and agent mentions.
type SuggestionEngine struct {
	commands []SuggestionItem
	agents   []SuggestionItem
}

// NewSuggestionEngine initializes default commands and known agent specialists.
func NewSuggestionEngine(agentIdentifiers []string) *SuggestionEngine {
	commands := []SuggestionItem{
		{Token: "/help", Title: "Help", Description: "Show available commands, agents, and keybindings", Kind: KindSlashCommand},
		{Token: "/status", Title: "Status", Description: "Inspect memory, active goroutines, and gateway health", Kind: KindSlashCommand},
		{Token: "/switch", Title: "Switch Agent", Description: "Set session focus to an agent (e.g. /switch browser)", Kind: KindSlashCommand},
		{Token: "/daemons", Title: "Daemons", Description: "List and manage background supervisor daemons", Kind: KindSlashCommand},
		{Token: "/models", Title: "Models", Description: "List Google GenAI models and active assignments", Kind: KindSlashCommand},
		{Token: "/checkpoint", Title: "Checkpoint", Description: "Save an immediate state snapshot of the active session", Kind: KindSlashCommand},
		{Token: "/clear", Title: "Clear", Description: "Clear the response screen conversation history", Kind: KindSlashCommand},
		{Token: "/exit", Title: "Exit", Description: "Safely restore terminal and terminate session", Kind: KindSlashCommand},
	}

	agentItems := []SuggestionItem{
		{Token: "@manager", Title: "Manager", Description: "Cognitive orchestrator & topological task planner (default)", Kind: KindAgentMention},
	}

	for _, id := range agentIdentifiers {
		clean := strings.ToLower(strings.TrimSpace(id))
		if clean == "" || clean == "manager" {
			continue
		}
		agentItems = append(agentItems, SuggestionItem{
			Token:       "@" + clean,
			Title:       strings.ToUpper(clean[:1]) + clean[1:],
			Description: "Direct prompt execution targeting @" + clean,
			Kind:        KindAgentMention,
		})
	}

	sort.Slice(commands, func(i, j int) bool { return commands[i].Token < commands[j].Token })
	sort.Slice(agentItems, func(i, j int) bool { return agentItems[i].Token < agentItems[j].Token })

	return &SuggestionEngine{
		commands: commands,
		agents:   agentItems,
	}
}

// Query finds all matching items given the full input text and the cursor position.
// It returns the list of matches, the active prefix word, and the start index of that word.
func (e *SuggestionEngine) Query(input []rune, cursor int) (matches []SuggestionItem, prefix string, wordStart int) {
	if cursor < 0 || cursor > len(input) {
		cursor = len(input)
	}

	// Find the start of the current word being typed before cursor
	wordStart = cursor
	for wordStart > 0 && !unicode.IsSpace(input[wordStart-1]) {
		wordStart--
	}

	currentWord := string(input[wordStart:cursor])
	if currentWord == "" {
		return nil, "", wordStart
	}

	// Match Slash Commands (only at start of line or standalone word starting with /)
	if strings.HasPrefix(currentWord, "/") {
		return filterByPrefix(e.commands, currentWord), currentWord, wordStart
	}

	// Match Agent Mentions (starts with @)
	if strings.HasPrefix(currentWord, "@") {
		return filterByPrefix(e.agents, currentWord), currentWord, wordStart
	}

	return nil, "", wordStart
}

func filterByPrefix(pool []SuggestionItem, prefix string) []SuggestionItem {
	lowerPrefix := strings.ToLower(prefix)
	var result []SuggestionItem
	for _, item := range pool {
		if strings.HasPrefix(strings.ToLower(item.Token), lowerPrefix) {
			result = append(result, item)
		}
	}
	return result
}

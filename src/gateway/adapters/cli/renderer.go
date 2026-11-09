package cli

import (
	"fmt"
	"strings"

	"assistant/src/gateway"
	"github.com/charmbracelet/lipgloss"
)

var (
	// Brand and Palette Styles
	BrandStyle   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#D97706"))   // Amber
	AgentStyle   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8"))   // Cyan
	ThoughtStyle = lipgloss.NewStyle().Italic(true).Foreground(lipgloss.Color("#64748B")) // Dim Slate
	StatusStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#A855F7"))              // Purple
	ErrorStyle   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#EF4444"))   // Red
	SuccessStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#34D399"))              // Emerald
	BoxBorder    = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).Padding(0, 1)
)

// RenderBanner creates the welcome header for the assistant CLI.
func RenderBanner(sessionID string) string {
	title := BrandStyle.Render("⚡ AI PERSONAL ASSISTANT — CONTROL PLANE")
	sub := lipgloss.NewStyle().Foreground(lipgloss.Color("#94A3B8")).Render("Layer 1 Gateway (Go) • Ready for input • Type /help for guidance")
	sess := lipgloss.NewStyle().Foreground(lipgloss.Color("#475569")).Render("Session: " + sessionID)
	return fmt.Sprintf("\n%s\n%s\n%s\n", title, sub, sess)
}

// RenderHelp returns formatted help text for slash commands and agent targeting.
func RenderHelp() string {
	var builder strings.Builder
	builder.WriteString(BrandStyle.Render("\nAvailable Commands & Syntax:\n"))
	builder.WriteString("  /help       - Display this assistance guide\n")
	builder.WriteString("  /session    - Display or inspect the current session ID\n")
	builder.WriteString("  /clear      - Clear the terminal screen\n")
	builder.WriteString("  /exit, /quit- Terminate the assistant session\n\n")
	builder.WriteString(AgentStyle.Render("Direct Agent Addressing:\n"))
	builder.WriteString("  @system <cmd>        - Invoke System Agent for local shell & OS commands\n")
	builder.WriteString("  @browser <query>     - Invoke Browser Agent for web automation\n")
	builder.WriteString("  @research <topic>    - Invoke Research Agent for deep investigation\n")
	builder.WriteString("  @productivity <task> - Invoke Productivity Agent for email/calendar\n")
	builder.WriteString("  <query>              - Auto-routed by Orchestrator\n")
	return builder.String()
}

// RenderThought formats internal agent reasoning chunks.
func RenderThought(agent string, text string) string {
	tag := ThoughtStyle.Render(fmt.Sprintf("[%s reasoning]", agent))
	content := ThoughtStyle.Render(text)
	return fmt.Sprintf("%s %s", tag, content)
}

// RenderStatus formats operational status notifications.
func RenderStatus(agent string, statusMsg string) string {
	badge := StatusStyle.Render("●")
	agentTag := AgentStyle.Render(agent)
	return fmt.Sprintf("%s %s: %s\n", badge, agentTag, statusMsg)
}

// RenderHITLPrompt formats an approval prompt for human clearance.
func RenderHITLPrompt(prompt *gateway.HITLApprovalPrompt) string {
	header := ErrorStyle.Render("⚠️  HUMAN APPROVAL REQUIRED")
	tool := fmt.Sprintf("Tool:   %s", AgentStyle.Render(prompt.ToolName))
	reason := fmt.Sprintf("Reason: %s", prompt.Reason)
	args := fmt.Sprintf("Args:   %s", prompt.ArgumentsJSON)
	promptText := BrandStyle.Render("Approve this action? [y/N]: ")

	content := fmt.Sprintf("%s\n%s\n%s\n%s\n\n%s", header, tool, reason, args, promptText)
	return BoxBorder.BorderForeground(lipgloss.Color("#F59E0B")).Render(content)
}

// RenderTurnMetrics formats telemetry metrics when a turn completes.
func RenderTurnMetrics(metrics *gateway.TurnMetrics) string {
	if metrics == nil {
		return ""
	}
	info := fmt.Sprintf(
		"Model: %s | Tokens: in=%d, out=%d, cached=%d | TTFT: %dms | Latency: %dms",
		metrics.ModelName,
		metrics.PromptTokens,
		metrics.CompletionTokens,
		metrics.CachedTokens,
		metrics.TimeToFirstByteMs,
		metrics.TotalDurationMs,
	)
	return lipgloss.NewStyle().Foreground(lipgloss.Color("#64748B")).Render("\n── " + info + " ──\n")
}

// RenderError formats error messages cleanly for terminal display.
func RenderError(errText string) string {
	return ErrorStyle.Render(fmt.Sprintf("\n✖ Error: %s\n", errText))
}

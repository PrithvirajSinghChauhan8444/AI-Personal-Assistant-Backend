package cli

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

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

// AgentBadge renders a color-coded agent identifier badge.
func AgentBadge(agent string) string {
	var color lipgloss.Color
	switch strings.ToLower(agent) {
	case "manager":
		color = lipgloss.Color("#F59E0B") // Amber
	case "scheduler":
		color = lipgloss.Color("#818CF8") // Indigo
	case "system", "systemagent":
		color = lipgloss.Color("#38BDF8") // Sky Cyan
	case "browser", "browseragent":
		color = lipgloss.Color("#34D399") // Emerald
	case "research", "researchagent":
		color = lipgloss.Color("#A855F7") // Purple
	case "productivity", "productivityagent":
		color = lipgloss.Color("#F472B6") // Pink
	case "orchestrator":
		color = lipgloss.Color("#FB923C") // Orange
	case "cli":
		color = lipgloss.Color("#94A3B8") // Slate
	default:
		color = lipgloss.Color("#38BDF8")
	}
	name := agent
	if name == "" {
		name = "Agent"
	}
	return lipgloss.NewStyle().Bold(true).Foreground(color).Render("[" + name + "]")
}

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
	tag := ThoughtStyle.Render(fmt.Sprintf("💭 [%s thought]", agent))
	content := ThoughtStyle.Render(strings.TrimSpace(text))
	return fmt.Sprintf("%s %s\n", tag, content)
}

// RenderThoughtHeader creates the opening indicator for streaming thoughts.
func RenderThoughtHeader(agent string) string {
	return ThoughtStyle.Render(fmt.Sprintf("💭 [%s thought] ", agent))
}

// RenderStatus formats operational status notifications in Claude Code style.
func RenderStatus(agent string, statusMsg string) string {
	timeStr := ThoughtStyle.Render(time.Now().Format("15:04:05"))
	agentBadge := AgentBadge(agent)

	var icon string
	switch {
	case strings.Contains(statusMsg, "completed successfully"):
		icon = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#34D399")).Render("✔")
	case strings.Contains(statusMsg, "failed") || strings.Contains(statusMsg, "error"):
		icon = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#EF4444")).Render("✖")
	case strings.HasPrefix(statusMsg, "Executing subtask"):
		icon = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8")).Render("➜")
	case strings.Contains(statusMsg, "spilled to artifact"):
		icon = lipgloss.NewStyle().Foreground(lipgloss.Color("#F59E0B")).Render("📁")
	case strings.HasPrefix(statusMsg, "Walking DAG") || strings.HasPrefix(statusMsg, "Decomposing"):
		icon = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#A855F7")).Render("✻")
	default:
		icon = StatusStyle.Render("●")
	}

	return fmt.Sprintf("%s %s %s %s\n", icon, timeStr, agentBadge, statusMsg)
}

// RenderHeartbeat formats an activity heartbeat indicator for ongoing operations.
func RenderHeartbeat(elapsed time.Duration) string {
	dot := StatusStyle.Render("⋯")
	timeStr := ThoughtStyle.Render(time.Now().Format("15:04:05"))
	msg := ThoughtStyle.Render(fmt.Sprintf("Still processing... (%s elapsed)", elapsed))
	return fmt.Sprintf("%s %s %s\n", dot, timeStr, msg)
}

// RenderToolCall formats an agent's tool invocation into a Claude Code styled block.
func RenderToolCall(agent, toolName, argsJSON, callID string) string {
	var builder strings.Builder
	borderStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#64748B"))
	toolStyle := lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#38BDF8"))
	argLabelStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#94A3B8"))
	argValStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#F1F5F9"))

	name := toolName
	if name == "" {
		name = "tool"
	}

	badge := AgentBadge(agent)
	header := fmt.Sprintf("%s 🛠  %s Tool Call: %s", borderStyle.Render("╭─"), badge, toolStyle.Render(name))
	builder.WriteString(header + "\n")

	// Parse arguments if valid JSON
	var parsedArgs map[string]any
	if argsJSON != "" && json.Unmarshal([]byte(argsJSON), &parsedArgs) == nil && len(parsedArgs) > 0 {
		primaryKeys := []string{"cmd", "command", "query", "url", "path", "file_path", "prompt", "pattern"}
		var primaryKey string
		for _, pk := range primaryKeys {
			if _, ok := parsedArgs[pk]; ok {
				primaryKey = pk
				break
			}
		}

		if primaryKey != "" {
			valStr := fmt.Sprintf("%v", parsedArgs[primaryKey])
			builder.WriteString(fmt.Sprintf("%s  %s: %s\n",
				borderStyle.Render("│"),
				argLabelStyle.Render(primaryKey),
				argValStyle.Render(valStr),
			))
		}

		count := 0
		for k, v := range parsedArgs {
			if k == primaryKey {
				continue
			}
			count++
			if count > 4 {
				builder.WriteString(fmt.Sprintf("%s  %s\n",
					borderStyle.Render("│"),
					argLabelStyle.Render("..."),
				))
				break
			}
			valBytes, _ := json.Marshal(v)
			builder.WriteString(fmt.Sprintf("%s  %s: %s\n",
				borderStyle.Render("│"),
				argLabelStyle.Render(k),
				argValStyle.Render(string(valBytes)),
			))
		}
	} else if argsJSON != "" && argsJSON != "{}" {
		truncated := argsJSON
		if len(truncated) > 160 {
			truncated = truncated[:157] + "..."
		}
		builder.WriteString(fmt.Sprintf("%s  %s: %s\n",
			borderStyle.Render("│"),
			argLabelStyle.Render("args"),
			argValStyle.Render(truncated),
		))
	}

	return builder.String()
}

// RenderToolResult formats tool execution completion into a Claude Code styled block.
func RenderToolResult(agent, toolName string, exitCode int, output, artifactPath string, durationMs int64, isError bool) string {
	var builder strings.Builder
	borderStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#64748B"))
	successGlyph := lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#34D399")).Render("✔")
	errorGlyph := lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#EF4444")).Render("✖")
	metaStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#94A3B8"))
	outputStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#CBD5E1"))
	artifactStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#F59E0B"))

	name := toolName
	if name == "" {
		name = "tool"
	}

	if isError || exitCode != 0 {
		statusText := fmt.Sprintf("%s failed (%dms", name, durationMs)
		if exitCode != 0 {
			statusText += fmt.Sprintf(", exit code %d", exitCode)
		}
		statusText += ")"
		builder.WriteString(fmt.Sprintf("%s %s %s\n",
			borderStyle.Render("╰─"),
			errorGlyph,
			lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#EF4444")).Render(statusText),
		))
		if output != "" {
			errPreview := strings.TrimSpace(output)
			lines := strings.Split(errPreview, "\n")
			for i, l := range lines {
				if i >= 3 {
					builder.WriteString(fmt.Sprintf("   %s\n", metaStyle.Render(fmt.Sprintf("... (%d more lines)", len(lines)-3))))
					break
				}
				builder.WriteString(fmt.Sprintf("   %s\n", lipgloss.NewStyle().Foreground(lipgloss.Color("#FCA5A5")).Render(l)))
			}
		}
		return builder.String()
	}

	// Success case
	statusText := fmt.Sprintf("%s completed (%dms)", name, durationMs)
	builder.WriteString(fmt.Sprintf("%s %s %s\n",
		borderStyle.Render("╰─"),
		successGlyph,
		SuccessStyle.Render(statusText),
	))

	if artifactPath != "" {
		builder.WriteString(fmt.Sprintf("   %s %s\n",
			artifactStyle.Render("📁 Spilled to artifact:"),
			metaStyle.Render(artifactPath),
		))
	}

	if output != "" {
		trimmed := strings.TrimSpace(output)
		lines := strings.Split(trimmed, "\n")
		if len(lines) == 1 && len(lines[0]) <= 120 {
			builder.WriteString(fmt.Sprintf("   %s %s\n",
				metaStyle.Render("Output:"),
				outputStyle.Render(lines[0]),
			))
		} else if len(lines) > 0 {
			builder.WriteString(fmt.Sprintf("   %s\n",
				metaStyle.Render(fmt.Sprintf("Output (%d lines):", len(lines))),
			))
			maxShow := 3
			for i := 0; i < len(lines) && i < maxShow; i++ {
				linePreview := lines[i]
				if len(linePreview) > 120 {
					linePreview = linePreview[:117] + "..."
				}
				builder.WriteString(fmt.Sprintf("   %s %s\n",
					borderStyle.Render("│"),
					outputStyle.Render(linePreview),
				))
			}
			if len(lines) > maxShow {
				builder.WriteString(fmt.Sprintf("   %s %s\n",
					borderStyle.Render("│"),
					metaStyle.Render(fmt.Sprintf("... and %d more line(s)", len(lines)-maxShow)),
				))
			}
		}
	}

	return builder.String()
}

// RenderHITLPrompt formats an approval prompt for human clearance.
func RenderHITLPrompt(prompt *gateway.HITLApprovalPrompt) string {
	if prompt == nil {
		return ""
	}
	header := ErrorStyle.Render("⚠️  HUMAN APPROVAL REQUIRED")
	tool := fmt.Sprintf("Tool:   %s", AgentStyle.Render(prompt.ToolName))
	reason := fmt.Sprintf("Reason: %s", prompt.Reason)
	args := fmt.Sprintf("Args:   %s", prompt.ArgumentsJSON)
	promptText := BrandStyle.Render("Approve this action? [y/N]: ")

	content := fmt.Sprintf("%s\n%s\n%s\n%s\n\n%s", header, tool, reason, args, promptText)
	return BoxBorder.BorderForeground(lipgloss.Color("#F59E0B")).Render(content) + "\n"
}

// RenderTurnMetrics formats telemetry metrics when a turn completes.
func RenderTurnMetrics(metrics *gateway.TurnMetrics) string {
	if metrics == nil {
		return ""
	}
	durationStr := fmt.Sprintf("%dms", metrics.TotalDurationMs)
	if metrics.TotalDurationMs >= 1000 {
		durationStr = fmt.Sprintf("%.2fs", float64(metrics.TotalDurationMs)/1000.0)
	}

	modelStr := metrics.ModelName
	if modelStr == "" {
		modelStr = "assistant-pipeline"
	}

	info := fmt.Sprintf(
		"Model: %s | Tokens: in=%d, out=%d, cached=%d | TTFT: %dms | Duration: %s",
		modelStr,
		metrics.PromptTokens,
		metrics.CompletionTokens,
		metrics.CachedTokens,
		metrics.TimeToFirstByteMs,
		durationStr,
	)
	bar := lipgloss.NewStyle().Foreground(lipgloss.Color("#475569")).Render("── ")
	body := lipgloss.NewStyle().Foreground(lipgloss.Color("#94A3B8")).Render(info)
	end := lipgloss.NewStyle().Foreground(lipgloss.Color("#475569")).Render(" ──")
	return fmt.Sprintf("\n%s%s%s\n", bar, body, end)
}

// RenderError formats error messages cleanly for terminal display.
func RenderError(errText string) string {
	glyph := lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#EF4444")).Render("✖")
	msg := ErrorStyle.Render(fmt.Sprintf("Error: %s", errText))
	return fmt.Sprintf("\n%s %s\n", glyph, msg)
}

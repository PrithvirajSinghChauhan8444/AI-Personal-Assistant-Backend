package telegram

import (
	"fmt"
	"regexp"
	"strings"

	"assistant/src/gateway"
)

var codeFenceRegex = regexp.MustCompile("^```(\\w*)")

// SplitMessage partitions markdown text into chunks under maxLen, preserving code block fences.
func SplitMessage(text string, maxLen int) []string {
	if text == "" {
		return []string{""}
	}
	if maxLen <= 0 {
		maxLen = DefaultMaxMessageLength
	}
	if len(text) <= maxLen {
		return []string{text}
	}

	var chunks []string
	lines := strings.Split(text, "\n")
	var currentChunk strings.Builder
	inCodeBlock := false
	codeBlockLang := ""

	for _, line := range lines {
		lineWithNewline := line + "\n"
		isFence, lang := extractCodeFence(line)

		if currentChunk.Len()+len(lineWithNewline) > maxLen {
			if currentChunk.Len() > 0 {
				chunkText := currentChunk.String()
				if inCodeBlock {
					chunkText += "```\n"
					chunks = append(chunks, strings.TrimSpace(chunkText))
					currentChunk.Reset()
					currentChunk.WriteString(fmt.Sprintf("```%s\n%s", codeBlockLang, lineWithNewline))
				} else {
					chunks = append(chunks, strings.TrimSpace(chunkText))
					currentChunk.Reset()
					currentChunk.WriteString(lineWithNewline)
				}
			} else {
				// Single line exceeds maxLen; slice directly
				for i := 0; i < len(line); i += maxLen {
					end := i + maxLen
					if end > len(line) {
						end = len(line)
					}
					chunks = append(chunks, line[i:end])
				}
			}
		} else {
			currentChunk.WriteString(lineWithNewline)
		}

		if isFence {
			inCodeBlock = !inCodeBlock
			if inCodeBlock {
				codeBlockLang = lang
			} else {
				codeBlockLang = ""
			}
		}
	}

	if currentChunk.Len() > 0 {
		tail := currentChunk.String()
		if inCodeBlock && !strings.HasSuffix(strings.TrimSpace(tail), "```") {
			tail += "\n```"
		}
		trimmed := strings.TrimSpace(tail)
		if trimmed != "" {
			chunks = append(chunks, trimmed)
		}
	}

	return chunks
}

func extractCodeFence(line string) (bool, string) {
	trimmed := strings.TrimSpace(line)
	matches := codeFenceRegex.FindStringSubmatch(trimmed)
	if len(matches) > 0 {
		lang := ""
		if len(matches) > 1 {
			lang = matches[1]
		}
		return true, lang
	}
	return false, ""
}

// FormatStatus renders a human-readable Telegram markdown status box.
func FormatStatus(phase gateway.ExecutionPhase, planSummary, activeWorker, activeSubtask, activeTool string) string {
	var sb strings.Builder
	sb.WriteString("🤖 *AI Assistant — Processing*\n")
	sb.WriteString(fmt.Sprintf("• *Phase:* `%s`\n", phase))

	if planSummary != "" {
		sb.WriteString(fmt.Sprintf("• *Plan:* %s\n", planSummary))
	}
	if activeWorker != "" {
		sb.WriteString(fmt.Sprintf("• *Active Worker:* `%s`\n", activeWorker))
	}
	if activeSubtask != "" {
		sb.WriteString(fmt.Sprintf("• *Task:* %s\n", activeSubtask))
	}
	if activeTool != "" {
		sb.WriteString(fmt.Sprintf("• *Tool in flight:* 🛠 `%s`\n", activeTool))
	}

	return sb.String()
}

// FormatHITLPrompt builds a high-visibility approval message with inline action buttons.
func FormatHITLPrompt(hitl *gateway.HITLApprovalPrompt) (string, *InlineKeyboardMarkup) {
	if hitl == nil {
		return "", nil
	}

	text := fmt.Sprintf("⚠️ *Approval Required*\n\nTool: `%s`\nReason: %s\n\n_Choose an option below or reply with Approve / Deny:_",
		hitl.ToolName, hitl.Reason)

	markup := &InlineKeyboardMarkup{
		InlineKeyboard: [][]InlineKeyboardButton{
			{
				{Text: "✅ Approve", CallbackData: fmt.Sprintf("hitl:approve:%s", hitl.RequestID)},
				{Text: "❌ Deny", CallbackData: fmt.Sprintf("hitl:deny:%s", hitl.RequestID)},
			},
		},
	}

	return text, markup
}

// FormatMetrics formats token consumption and execution duration into a footer line.
func FormatMetrics(metrics *gateway.TurnMetrics) string {
	if metrics == nil {
		return ""
	}
	return fmt.Sprintf("📊 _Duration: %dms | Tokens: in=%d, out=%d_",
		metrics.TotalDurationMs, metrics.PromptTokens, metrics.CompletionTokens)
}

// FormatHelp returns command usage documentation.
func FormatHelp() string {
	return `🤖 *AI Assistant — Telegram Gateway Commands*

• Send any text prompt to initiate an interactive turn.
• */reset* or */clear* — Start a fresh conversation session.
• */status* — View live execution phase and active tasks.
• */approve* ` + "`[reason]`" + ` — Authorize a paused HITL tool execution.
• */deny* ` + "`[reason]`" + ` — Reject a pending HITL tool execution.
• */help* — Show this guidance menu.`
}

// FormatAccessDenied returns a security rejection message displaying the numeric ID.
func FormatAccessDenied(userID int64) string {
	return fmt.Sprintf("⛔ *Access Denied*\n\nYour Telegram User ID is: `%d`\nFor security, please add this ID to `TELEGRAM_ALLOWED_USER_IDS` in your configuration.", userID)
}

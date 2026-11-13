package gmail

import (
	"fmt"
	"net/mail"
	"regexp"
	"strings"
	"time"

	"assistant/src/gateway"
)

var emailRegex = regexp.MustCompile(`[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+`)

// EmailClassifier determines execution policies and constructs normalized inbound turns.
type EmailClassifier struct {
	verifiedEmails map[string]bool
}

// NewEmailClassifier creates an EmailClassifier with known user email addresses.
func NewEmailClassifier(userEmails []string) *EmailClassifier {
	verified := make(map[string]bool, len(userEmails))
	for _, email := range userEmails {
		clean := ExtractAddress(email)
		if clean != "" {
			verified[clean] = true
		}
	}
	return &EmailClassifier{verifiedEmails: verified}
}

// ExtractAddress extracts a normalized lowercase email address from header strings.
func ExtractAddress(raw string) string {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return ""
	}

	if parsed, err := mail.ParseAddress(trimmed); err == nil && parsed.Address != "" {
		return strings.ToLower(parsed.Address)
	}

	if match := emailRegex.FindString(trimmed); match != "" {
		return strings.ToLower(match)
	}

	return ""
}

// IsSelfMail reports whether the sender address matches any verified user address.
func (c *EmailClassifier) IsSelfMail(sender string) bool {
	cleanSender := ExtractAddress(sender)
	if cleanSender == "" {
		return false
	}
	return c.verifiedEmails[cleanSender]
}

// RegisterEmail registers an additional verified user email address.
func (c *EmailClassifier) RegisterEmail(email string) {
	clean := ExtractAddress(email)
	if clean != "" {
		c.verifiedEmails[clean] = true
	}
}

// BuildInboundTurn creates an InboundTurnRequest tailored to the email sender trust level.
func (c *EmailClassifier) BuildInboundTurn(msg EmailSummary) gateway.InboundTurnRequest {
	if c.IsSelfMail(msg.From) {
		return c.buildSelfMailTurn(msg)
	}
	return c.buildExternalMailTurn(msg)
}

func (c *EmailClassifier) buildSelfMailTurn(msg EmailSummary) gateway.InboundTurnRequest {
	prompt := formatSelfMailPrompt(msg)
	capabilities := selfMailCapabilities()

	return gateway.InboundTurnRequest{
		Channel:             gateway.ClientTypeInternal,
		Trigger:             gateway.TriggerAutonomous,
		AllowedCapabilities: capabilities,
		TargetAgent:         "auto",
		ReceivedAt:          time.Now().UTC(),
		Prompt:              prompt,
	}
}

func (c *EmailClassifier) buildExternalMailTurn(msg EmailSummary) gateway.InboundTurnRequest {
	prompt := formatExternalTriagePrompt(msg)
	capabilities := externalMailCapabilities()

	return gateway.InboundTurnRequest{
		Channel:             gateway.ClientTypeInternal,
		Trigger:             gateway.TriggerAutonomous,
		AllowedCapabilities: capabilities,
		TargetAgent:         "productivity",
		ReceivedAt:          time.Now().UTC(),
		Prompt:              prompt,
	}
}

func formatSelfMailPrompt(msg EmailSummary) string {
	subject := strings.TrimSpace(msg.Subject)
	body := strings.TrimSpace(msg.Body)
	if body == "" {
		body = strings.TrimSpace(msg.Snippet)
	}

	if subject != "" && subject != "(No Subject)" {
		if body != "" {
			return fmt.Sprintf("%s\n\n%s", subject, body)
		}
		return subject
	}
	return body
}

func formatExternalTriagePrompt(msg EmailSummary) string {
	body := msg.Body
	if body == "" {
		body = msg.Snippet
	}
	if len(body) > 2000 {
		body = body[:2000] + "..."
	}

	return fmt.Sprintf(
		"New incoming email received in account '%s':\n"+
			"From: %s\n"+
			"Subject: %s\n"+
			"MessageID: %s\n\n"+
			"Content:\n%s\n\n"+
			"Instructions: Review this email. If actionable, stage a courteous reply draft "+
			"using gmail_send_draft. Do not send directly and do not execute external commands.",
		msg.Account, msg.From, msg.Subject, msg.ID, body,
	)
}

func selfMailCapabilities() []string {
	return []string{
		"gmail_read",
		"gmail_list",
		"gmail_send_draft",
		"calendar_read",
		"calendar_list",
		"calendar_create_event",
		"fs_read",
		"fs_write",
		"fs_list",
		"net_search",
		"sys_exec",
	}
}

func externalMailCapabilities() []string {
	return []string{
		"gmail_read",
		"gmail_list",
		"gmail_send_draft",
	}
}

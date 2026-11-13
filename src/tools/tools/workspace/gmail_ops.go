package workspace

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"assistant/src/tools"
)

// GmailReplyArgs defines parameters to reply to an email thread.
type GmailReplyArgs struct {
	Account   string `json:"account,omitempty"`
	MessageID string `json:"message_id"`
	Body      string `json:"body"`
}

// GmailCheckUnreadArgs defines parameters to query unread emails.
type GmailCheckUnreadArgs struct {
	Account string `json:"account,omitempty"`
	Limit   int    `json:"limit,omitempty"`
}

// GmailSendArgs defines parameters to dispatch an email immediately.
type GmailSendArgs struct {
	Account string `json:"account,omitempty"`
	To      string `json:"to"`
	Subject string `json:"subject"`
	Body    string `json:"body"`
}

// GmailReplyTool replies to an existing email thread.
type GmailReplyTool struct {
	client *GoogleClient
}

func NewGmailReplyTool(client *GoogleClient) *GmailReplyTool {
	return &GmailReplyTool{client: client}
}

func (t *GmailReplyTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "gmail_reply",
		Category:    "workspace",
		Description: "Replies directly to an existing email thread, preserving In-Reply-To, References, and Thread ID.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Account alias or email"},
				"message_id": {"type": "string", "description": "Original Gmail message ID to reply to"},
				"body": {"type": "string", "description": "Reply email body content"}
			},
			"required": ["message_id", "body"]
		}`,
		PromptUsageTip:     "Use gmail_reply when responding to an email thread. Prefer drafting first unless direct reply is instructed.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "workspace:write",
	}
}

func (t *GmailReplyTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GmailReplyArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	if strings.TrimSpace(args.MessageID) == "" || strings.TrimSpace(args.Body) == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "'message_id' and 'body' are required"}, nil
	}

	// 1. Fetch original message headers
	metaEndpoint := fmt.Sprintf("https://gmail.googleapis.com/gmail/v1/users/me/messages/%s?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Message-ID",
		args.MessageID)

	metaResp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, metaEndpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to fetch original email metadata: %v", err)}, nil
	}
	defer metaResp.Body.Close()

	if metaResp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(metaResp.Body)
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to fetch original message (%d): %s", metaResp.StatusCode, string(body))}, nil
	}

	var origMsg struct {
		ThreadID string `json:"threadId"`
		Payload  struct {
			Headers []struct {
				Name  string `json:"name"`
				Value string `json:"value"`
			} `json:"headers"`
		} `json:"payload"`
	}

	if err := json.NewDecoder(metaResp.Body).Decode(&origMsg); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to parse email metadata: %v", err)}, nil
	}

	var origFrom, origSubject, origMessageID string
	for _, h := range origMsg.Payload.Headers {
		switch strings.ToLower(h.Name) {
		case "from":
			origFrom = h.Value
		case "subject":
			origSubject = h.Value
		case "message-id":
			origMessageID = h.Value
		}
	}

	if origFrom == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "unable to determine sender from original message"}, nil
	}

	subject := origSubject
	if !strings.HasPrefix(strings.ToLower(subject), "re:") {
		subject = "Re: " + subject
	}

	// 2. Build RFC 822 reply
	var rfc822 strings.Builder
	rfc822.WriteString(fmt.Sprintf("To: %s\r\n", origFrom))
	rfc822.WriteString(fmt.Sprintf("Subject: %s\r\n", subject))
	if origMessageID != "" {
		rfc822.WriteString(fmt.Sprintf("In-Reply-To: %s\r\n", origMessageID))
		rfc822.WriteString(fmt.Sprintf("References: %s\r\n", origMessageID))
	}
	rfc822.WriteString("Content-Type: text/plain; charset=UTF-8\r\n\r\n")
	rfc822.WriteString(args.Body)

	rawBase64 := base64.URLEncoding.EncodeToString([]byte(rfc822.String()))
	sendPayload := map[string]string{
		"raw":      rawBase64,
		"threadId": origMsg.ThreadID,
	}

	payloadBytes, _ := json.Marshal(sendPayload)
	sendEndpoint := "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

	sendResp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodPost, sendEndpoint, bytes.NewReader(payloadBytes))
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to send reply: %v", err)}, nil
	}
	defer sendResp.Body.Close()

	respBody, _ := io.ReadAll(sendResp.Body)
	if sendResp.StatusCode != http.StatusOK {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Gmail reply send error (%d): %s", sendResp.StatusCode, string(respBody))}, nil
	}

	return &tools.ToolResult{Stdout: fmt.Sprintf("Successfully replied to thread %s: %s", origMsg.ThreadID, string(respBody))}, nil
}

// GmailCheckUnreadTool scans for unread emails and returns summaries.
type GmailCheckUnreadTool struct {
	client *GoogleClient
}

func NewGmailCheckUnreadTool(client *GoogleClient) *GmailCheckUnreadTool {
	return &GmailCheckUnreadTool{client: client}
}

func (t *GmailCheckUnreadTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "gmail_check_unread",
		Category:    "workspace",
		Description: "Fetches count and headers of unread emails.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Account alias or email"},
				"limit": {"type": "integer", "description": "Maximum unread emails to retrieve (default: 5)"}
			}
		}`,
		PromptUsageTip:     "Use gmail_check_unread during briefings or proactive notifications to triage incoming mail.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *GmailCheckUnreadTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GmailCheckUnreadArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	limit := args.Limit
	if limit <= 0 {
		limit = 5
	} else if limit > 25 {
		limit = 25
	}

	listURL := fmt.Sprintf("https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=%d", limit)
	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, listURL, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to check unread emails: %v", err)}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Gmail API error (%d): %s", resp.StatusCode, string(body))}, nil
	}

	var listData struct {
		ResultSizeEstimate int `json:"resultSizeEstimate"`
		Messages           []struct {
			ID string `json:"id"`
		} `json:"messages"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&listData); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to decode unread list: %v", err)}, nil
	}

	if len(listData.Messages) == 0 {
		return &tools.ToolResult{Stdout: "No unread emails found."}, nil
	}

	summaries := make([]GmailMessageItem, 0, len(listData.Messages))
	for _, m := range listData.Messages {
		getURL := fmt.Sprintf("https://gmail.googleapis.com/gmail/v1/users/me/messages/%s?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date", m.ID)
		msgResp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, getURL, nil)
		if err != nil {
			continue
		}

		var item struct {
			ID      string `json:"id"`
			Snippet string `json:"snippet"`
			Payload struct {
				Headers []struct {
					Name  string `json:"name"`
					Value string `json:"value"`
				} `json:"headers"`
			} `json:"payload"`
		}

		if err := json.NewDecoder(msgResp.Body).Decode(&item); err == nil {
			summary := GmailMessageItem{
				ID:      item.ID,
				Snippet: item.Snippet,
			}
			for _, h := range item.Payload.Headers {
				switch strings.ToLower(h.Name) {
				case "from":
					summary.From = h.Value
				case "subject":
					summary.Subject = h.Value
				case "date":
					summary.Date = h.Value
				}
			}
			summaries = append(summaries, summary)
		}
		msgResp.Body.Close()
	}

	resultMap := map[string]any{
		"unread_count": len(listData.Messages),
		"messages":     summaries,
	}

	resultBytes, _ := json.MarshalIndent(resultMap, "", "  ")
	return &tools.ToolResult{Stdout: string(resultBytes)}, nil
}

// GmailSendTool sends an email directly without drafting.
type GmailSendTool struct {
	client *GoogleClient
}

func NewGmailSendTool(client *GoogleClient) *GmailSendTool {
	return &GmailSendTool{client: client}
}

func (t *GmailSendTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "gmail_send",
		Category:    "workspace",
		Description: "Dispatches an email directly to a recipient. Requires high authorization.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Account alias or email"},
				"to": {"type": "string", "description": "Recipient email address"},
				"subject": {"type": "string", "description": "Email subject"},
				"body": {"type": "string", "description": "Email body content"}
			},
			"required": ["to", "subject", "body"]
		}`,
		PromptUsageTip:     "Use gmail_send only when direct sending without a draft is explicitly authorized.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "workspace:write",
	}
}

func (t *GmailSendTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GmailSendArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	if strings.TrimSpace(args.To) == "" || strings.TrimSpace(args.Subject) == "" || strings.TrimSpace(args.Body) == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "'to', 'subject', and 'body' are all required"}, nil
	}

	rawRFC822 := fmt.Sprintf("To: %s\r\nSubject: %s\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n%s",
		args.To, args.Subject, args.Body)
	rawBase64 := base64.URLEncoding.EncodeToString([]byte(rawRFC822))

	payload := map[string]string{
		"raw": rawBase64,
	}
	payloadBytes, _ := json.Marshal(payload)

	endpoint := "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodPost, endpoint, bytes.NewReader(payloadBytes))
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to send email: %v", err)}, nil
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Gmail API error (%d): %s", resp.StatusCode, string(respBody))}, nil
	}

	return &tools.ToolResult{Stdout: fmt.Sprintf("Email sent successfully: %s", string(respBody))}, nil
}

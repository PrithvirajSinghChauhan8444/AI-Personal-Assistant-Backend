package workspace

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"assistant/src/tools"
)

type GmailReadArgs struct {
	Account   string `json:"account,omitempty"`
	MessageID string `json:"message_id"`
}

type GmailReadResult struct {
	ID      string `json:"id"`
	Subject string `json:"subject"`
	From    string `json:"from"`
	To      string `json:"to"`
	Date    string `json:"date"`
	Body    string `json:"body"`
}

type GmailReadTool struct {
	client *GoogleClient
}

func NewGmailReadTool(client *GoogleClient) *GmailReadTool {
	return &GmailReadTool{client: client}
}

func (t *GmailReadTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "gmail_read",
		Category:           "workspace",
		Description:        "Reads full email headers and decoded body content for a specific message ID.",
		ParameterSchema:    `{"type":"object","properties":{"account":{"type":"string","description":"Account alias or email (primary, college, personal)"},"message_id":{"type":"string","description":"Gmail message ID returned from gmail_list"}},"required":["message_id"]}`,
		PromptUsageTip:     "Use gmail_read after obtaining message IDs from gmail_list to review full email conversations.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *GmailReadTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GmailReadArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for gmail_read: %v", err),
		}, nil
	}

	if strings.TrimSpace(args.MessageID) == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "message_id cannot be empty",
		}, nil
	}

	endpoint := fmt.Sprintf("https://gmail.googleapis.com/gmail/v1/users/me/messages/%s?format=full", args.MessageID)
	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to fetch message: %v", err),
		}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("Gmail API error (%d): %s", resp.StatusCode, string(body)),
		}, nil
	}

	var detail struct {
		ID      string `json:"id"`
		Payload struct {
			MimeType string `json:"mimeType"`
			Headers  []struct {
				Name  string `json:"name"`
				Value string `json:"value"`
			} `json:"headers"`
			Body struct {
				Data string `json:"data"`
			} `json:"body"`
			Parts []struct {
				MimeType string `json:"mimeType"`
				Body     struct {
					Data string `json:"data"`
				} `json:"body"`
			} `json:"parts"`
		} `json:"payload"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&detail); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed parsing message body: %v", err),
		}, nil
	}

	result := GmailReadResult{ID: detail.ID}
	for _, h := range detail.Payload.Headers {
		switch strings.ToLower(h.Name) {
		case "subject":
			result.Subject = h.Value
		case "from":
			result.From = h.Value
		case "to":
			result.To = h.Value
		case "date":
			result.Date = h.Value
		}
	}

	result.Body = extractMessageBody(detail.Payload.Body.Data, detail.Payload.Parts)

	outJSON, _ := json.MarshalIndent(result, "", "  ")
	return &tools.ToolResult{
		Stdout:   string(outJSON),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func extractMessageBody(directData string, parts []struct {
	MimeType string `json:"mimeType"`
	Body     struct {
		Data string `json:"data"`
	} `json:"body"`
}) string {
	if directData != "" {
		if decoded, err := decodeBase64URL(directData); err == nil {
			return string(decoded)
		}
	}

	for _, p := range parts {
		if p.MimeType == "text/plain" && p.Body.Data != "" {
			if decoded, err := decodeBase64URL(p.Body.Data); err == nil {
				return string(decoded)
			}
		}
	}

	for _, p := range parts {
		if p.MimeType == "text/html" && p.Body.Data != "" {
			if decoded, err := decodeBase64URL(p.Body.Data); err == nil {
				return string(decoded)
			}
		}
	}

	return "(empty message body)"
}

func decodeBase64URL(encoded string) ([]byte, error) {
	s := strings.ReplaceAll(encoded, "-", "+")
	s = strings.ReplaceAll(s, "_", "/")
	switch len(s) % 4 {
	case 2:
		s += "=="
	case 3:
		s += "="
	}
	return base64.StdEncoding.DecodeString(s)
}

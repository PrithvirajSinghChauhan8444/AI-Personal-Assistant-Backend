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

type GmailSendDraftArgs struct {
	Account string `json:"account,omitempty"`
	To      string `json:"to"`
	Subject string `json:"subject"`
	Body    string `json:"body"`
}

type GmailSendDraftTool struct {
	client *GoogleClient
}

func NewGmailSendDraftTool(client *GoogleClient) *GmailSendDraftTool {
	return &GmailSendDraftTool{client: client}
}

func (t *GmailSendDraftTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "gmail_send_draft",
		Category:           "workspace",
		Description:        "Creates a new email draft in Gmail without sending it immediately.",
		ParameterSchema:    `{"type":"object","properties":{"account":{"type":"string","description":"Account alias or email (primary, college, personal)"},"to":{"type":"string","description":"Recipient email address"},"subject":{"type":"string","description":"Email subject line"},"body":{"type":"string","description":"Email message body"}},"required":["to","subject","body"]}`,
		PromptUsageTip:     "Use gmail_send_draft to prepare email communications. Drafts allow user review before dispatch.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "workspace:write",
	}
}

func (t *GmailSendDraftTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GmailSendDraftArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for gmail_send_draft: %v", err),
		}, nil
	}

	if strings.TrimSpace(args.To) == "" || strings.TrimSpace(args.Subject) == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "'to' and 'subject' cannot be empty",
		}, nil
	}

	rawRFC822 := fmt.Sprintf("To: %s\r\nSubject: %s\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n%s",
		args.To, args.Subject, args.Body)
	rawBase64 := base64.URLEncoding.EncodeToString([]byte(rawRFC822))

	payload := map[string]any{
		"message": map[string]string{
			"raw": rawBase64,
		},
	}
	payloadBytes, _ := json.Marshal(payload)

	endpoint := "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodPost, endpoint, bytes.NewReader(payloadBytes))
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to create draft: %v", err),
		}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("Gmail API draft creation error (%d): %s", resp.StatusCode, string(body)),
		}, nil
	}

	var draftResp struct {
		ID      string `json:"id"`
		Message struct {
			ID string `json:"id"`
		} `json:"message"`
	}
	_ = json.NewDecoder(resp.Body).Decode(&draftResp)

	return &tools.ToolResult{
		Stdout:   fmt.Sprintf("Draft created successfully. Draft ID: %s, Message ID: %s", draftResp.ID, draftResp.Message.ID),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

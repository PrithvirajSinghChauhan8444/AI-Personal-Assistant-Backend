package workspace

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"

	"assistant/src/tools"
)

type GmailListArgs struct {
	Account string `json:"account,omitempty"`
	Query   string `json:"query,omitempty"`
	Limit   int    `json:"limit,omitempty"`
}

type GmailMessageItem struct {
	ID      string `json:"id"`
	Snippet string `json:"snippet"`
	Subject string `json:"subject"`
	From    string `json:"from"`
	Date    string `json:"date"`
}

type GmailListTool struct {
	client *GoogleClient
}

func NewGmailListTool(client *GoogleClient) *GmailListTool {
	return &GmailListTool{client: client}
}

func (t *GmailListTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "gmail_list",
		Category:           "workspace",
		Description:        "Lists recent emails matching query via Google Workspace OAuth client.",
		ParameterSchema:    `{"type":"object","properties":{"account":{"type":"string","description":"Account alias or email (primary, college, personal)"},"query":{"type":"string","description":"Gmail search query (e.g. 'is:unread', 'from:github', default: 'in:inbox')"},"limit":{"type":"integer","description":"Maximum emails to retrieve (default: 10)"}}}`,
		PromptUsageTip:     "Use gmail_list to check incoming mail, search for notifications, or locate message IDs for gmail_read.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *GmailListTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GmailListArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	query := args.Query
	if query == "" {
		query = "in:inbox"
	}

	limit := args.Limit
	if limit <= 0 {
		limit = 10
	} else if limit > 50 {
		limit = 50
	}

	listURL := fmt.Sprintf("https://gmail.googleapis.com/gmail/v1/users/me/messages?q=%s&maxResults=%d",
		url.QueryEscape(query), limit)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, listURL, nil)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to query Gmail API: %v", err),
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

	var listData struct {
		Messages []struct {
			ID string `json:"id"`
		} `json:"messages"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&listData); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to parse Gmail list response: %v", err),
		}, nil
	}

	if len(listData.Messages) == 0 {
		return &tools.ToolResult{
			Stdout:   fmt.Sprintf("No messages found matching query: %s", query),
			ExitCode: 0,
			IsError:  false,
		}, nil
	}

	items := t.fetchMessageSummaries(ctx, args.Account, listData.Messages)
	outJSON, _ := json.MarshalIndent(items, "", "  ")

	return &tools.ToolResult{
		Stdout:   string(outJSON),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func (t *GmailListTool) fetchMessageSummaries(ctx context.Context, account string, msgs []struct{ ID string `json:"id"` }) []GmailMessageItem {
	var items []GmailMessageItem

	for _, m := range msgs {
		msgURL := fmt.Sprintf("https://gmail.googleapis.com/gmail/v1/users/me/messages/%s?format=metadata&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=Date", m.ID)
		resp, err := t.client.DoAuthorizedRequest(ctx, account, http.MethodGet, msgURL, nil)
		if err != nil {
			continue
		}

		var detail struct {
			ID      string `json:"id"`
			Snippet string `json:"snippet"`
			Payload struct {
				Headers []struct {
					Name  string `json:"name"`
					Value string `json:"value"`
				} `json:"headers"`
			} `json:"payload"`
		}

		if err := json.NewDecoder(resp.Body).Decode(&detail); err == nil {
			item := GmailMessageItem{
				ID:      detail.ID,
				Snippet: detail.Snippet,
			}
			for _, h := range detail.Payload.Headers {
				switch strings.ToLower(h.Name) {
				case "subject":
					item.Subject = h.Value
				case "from":
					item.From = h.Value
				case "date":
					item.Date = h.Value
				}
			}
			items = append(items, item)
		}
		resp.Body.Close()
	}

	return items
}

package workspace

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"assistant/src/tools"
)

type CalendarListArgs struct {
	Account string `json:"account,omitempty"`
	TimeMin string `json:"time_min,omitempty"`
	TimeMax string `json:"time_max,omitempty"`
	Limit   int    `json:"limit,omitempty"`
}

type CalendarEventItem struct {
	ID       string `json:"id"`
	Summary  string `json:"summary"`
	Start    string `json:"start"`
	End      string `json:"end"`
	Location string `json:"location,omitempty"`
	Status   string `json:"status"`
}

type CalendarListTool struct {
	client *GoogleClient
}

func NewCalendarListTool(client *GoogleClient) *CalendarListTool {
	return &CalendarListTool{client: client}
}

func (t *CalendarListTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "calendar_list",
		Category:           "workspace",
		Description:        "Lists scheduled Google Calendar events within a specified time window.",
		ParameterSchema:    `{"type":"object","properties":{"account":{"type":"string","description":"Account alias or email (primary, college, personal)"},"time_min":{"type":"string","description":"RFC3339 timestamp filter start (default: start of today)"},"time_max":{"type":"string","description":"RFC3339 timestamp filter end (default: 7 days ahead)"},"limit":{"type":"integer","description":"Maximum events to return (default: 10)"}}}`,
		PromptUsageTip:     "Use calendar_list to check schedules, meetings, and upcoming deadlines.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *CalendarListTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args CalendarListArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	timeMin := args.TimeMin
	if timeMin == "" {
		timeMin = time.Now().Truncate(24 * time.Hour).Format(time.RFC3339)
	}

	timeMax := args.TimeMax
	if timeMax == "" {
		timeMax = time.Now().Add(7 * 24 * time.Hour).Format(time.RFC3339)
	}

	limit := args.Limit
	if limit <= 0 {
		limit = 10
	} else if limit > 50 {
		limit = 50
	}

	endpoint := fmt.Sprintf("https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin=%s&timeMax=%s&maxResults=%d&singleEvents=true&orderBy=startTime",
		url.QueryEscape(timeMin), url.QueryEscape(timeMax), limit)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to query Calendar API: %v", err),
		}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("Calendar API error (%d): %s", resp.StatusCode, string(body)),
		}, nil
	}

	var calResp struct {
		Items []struct {
			ID       string `json:"id"`
			Summary  string `json:"summary"`
			Status   string `json:"status"`
			Location string `json:"location"`
			Start    struct {
				DateTime string `json:"dateTime"`
				Date     string `json:"date"`
			} `json:"start"`
			End struct {
				DateTime string `json:"dateTime"`
				Date     string `json:"date"`
			} `json:"end"`
		} `json:"items"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&calResp); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed parsing calendar events: %v", err),
		}, nil
	}

	if len(calResp.Items) == 0 {
		return &tools.ToolResult{
			Stdout:   "No calendar events found in the specified time window.",
			ExitCode: 0,
			IsError:  false,
		}, nil
	}

	var eventItems []CalendarEventItem
	for _, item := range calResp.Items {
		startTime := item.Start.DateTime
		if startTime == "" {
			startTime = item.Start.Date
		}
		endTime := item.End.DateTime
		if endTime == "" {
			endTime = item.End.Date
		}

		eventItems = append(eventItems, CalendarEventItem{
			ID:       item.ID,
			Summary:  item.Summary,
			Start:    startTime,
			End:      endTime,
			Location: item.Location,
			Status:   item.Status,
		})
	}

	outJSON, _ := json.MarshalIndent(eventItems, "", "  ")
	return &tools.ToolResult{
		Stdout:   string(outJSON),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

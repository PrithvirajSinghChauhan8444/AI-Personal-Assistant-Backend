package workspace

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"assistant/src/tools"
)

// CalendarCreateEventArgs defines input parameters for creating a Google Calendar event.
type CalendarCreateEventArgs struct {
	Account       string  `json:"account,omitempty"`
	Summary       string  `json:"summary"`
	StartTime     string  `json:"start_time"`
	DurationHours float64 `json:"duration_hours,omitempty"`
	Description   string  `json:"description,omitempty"`
	Color         string  `json:"color,omitempty"`
}

// CalendarEditEventArgs defines input parameters for editing an existing event.
type CalendarEditEventArgs struct {
	Account       string   `json:"account,omitempty"`
	EventID       string   `json:"event_id"`
	Summary       *string  `json:"summary,omitempty"`
	StartTime     *string  `json:"start_time,omitempty"`
	DurationHours *float64 `json:"duration_hours,omitempty"`
	Description   *string  `json:"description,omitempty"`
	Color         *string  `json:"color,omitempty"`
}

// CalendarDeleteEventArgs defines input parameters for deleting an event.
type CalendarDeleteEventArgs struct {
	Account string `json:"account,omitempty"`
	EventID string `json:"event_id"`
}

// calendarColorMap maps friendly color names to Google Calendar colorId strings.
var calendarColorMap = map[string]string{
	"blue":      "1",
	"green":     "2",
	"purple":    "3",
	"red":       "4",
	"yellow":    "5",
	"orange":    "6",
	"turquoise": "7",
	"gray":      "8",
	"bold_blue": "9",
	"bold_green":"10",
	"bold_red":  "11",
}

func resolveCalendarColorID(color string) string {
	cleaned := strings.ToLower(strings.TrimSpace(color))
	if id, ok := calendarColorMap[cleaned]; ok {
		return id
	}
	if len(cleaned) > 0 && cleaned[0] >= '1' && cleaned[0] <= '9' {
		return cleaned
	}
	return "6" // default orange
}

func parseEventTimestamps(startTimeISO string, durationHours float64) (string, string, error) {
	if durationHours <= 0 {
		durationHours = 1.0
	}

	start, err := time.Parse(time.RFC3339, startTimeISO)
	if err != nil {
		start, err = time.Parse("2006-01-02T15:04:05", startTimeISO)
		if err != nil {
			start, err = time.Parse("2006-01-02T15:04", startTimeISO)
			if err != nil {
				return "", "", fmt.Errorf("invalid ISO/RFC3339 start_time format: %w", err)
			}
		}
	}

	durationNano := time.Duration(durationHours * float64(time.Hour))
	end := start.Add(durationNano)

	return start.Format(time.RFC3339), end.Format(time.RFC3339), nil
}

// CalendarCreateEventTool creates an event on Google Calendar.
type CalendarCreateEventTool struct {
	client *GoogleClient
}

func NewCalendarCreateEventTool(client *GoogleClient) *CalendarCreateEventTool {
	return &CalendarCreateEventTool{client: client}
}

func (t *CalendarCreateEventTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "calendar_create_event",
		Category:    "workspace",
		Description: "Creates a new event on Google Calendar with start time, duration, and details.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Account alias or email (primary, college, personal)"},
				"summary": {"type": "string", "description": "Title or summary of the event"},
				"start_time": {"type": "string", "description": "ISO/RFC3339 timestamp (e.g. '2026-11-14T10:00:00Z')"},
				"duration_hours": {"type": "number", "description": "Duration in hours (default: 1.0)"},
				"description": {"type": "string", "description": "Optional notes or meeting agenda"},
				"color": {"type": "string", "description": "Optional color name (blue, green, orange, red, purple)"}
			},
			"required": ["summary", "start_time"]
		}`,
		PromptUsageTip:     "Use calendar_create_event to schedule meetings and deadlines. Verify conflict with calendar_list first.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "workspace:write",
	}
}

func (t *CalendarCreateEventTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args CalendarCreateEventArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	if strings.TrimSpace(args.Summary) == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "'summary' cannot be empty"}, nil
	}

	startRFC, endRFC, err := parseEventTimestamps(args.StartTime, args.DurationHours)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: err.Error()}, nil
	}

	description := strings.TrimSpace(args.Description)
	if !strings.Contains(strings.ToLower(description), "ai assistant") {
		if description != "" {
			description += "\n\nThis event was scheduled by the AI assistant."
		} else {
			description = "This event was scheduled by the AI assistant."
		}
	}

	eventPayload := map[string]any{
		"summary":     args.Summary,
		"description": description,
		"start":       map[string]string{"dateTime": startRFC},
		"end":         map[string]string{"dateTime": endRFC},
	}
	if args.Color != "" {
		eventPayload["colorId"] = resolveCalendarColorID(args.Color)
	}

	bodyBytes, _ := json.Marshal(eventPayload)
	endpoint := "https://www.googleapis.com/calendar/v3/calendars/primary/events"

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodPost, endpoint, bytes.NewReader(bodyBytes))
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to create event: %v", err)}, nil
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Calendar API error (%d): %s", resp.StatusCode, string(respBody))}, nil
	}

	var created struct {
		ID       string `json:"id"`
		Summary  string `json:"summary"`
		HTMLLink string `json:"htmlLink"`
		Start    struct {
			DateTime string `json:"dateTime"`
		} `json:"start"`
		End struct {
			DateTime string `json:"dateTime"`
		} `json:"end"`
	}
	_ = json.Unmarshal(respBody, &created)

	resultJSON, _ := json.MarshalIndent(map[string]any{
		"status":    "created",
		"id":        created.ID,
		"summary":   created.Summary,
		"start":     created.Start.DateTime,
		"end":       created.End.DateTime,
		"html_link": created.HTMLLink,
	}, "", "  ")

	return &tools.ToolResult{Stdout: string(resultJSON)}, nil
}

// CalendarEditEventTool modifies an existing Google Calendar event.
type CalendarEditEventTool struct {
	client *GoogleClient
}

func NewCalendarEditEventTool(client *GoogleClient) *CalendarEditEventTool {
	return &CalendarEditEventTool{client: client}
}

func (t *CalendarEditEventTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "calendar_edit_event",
		Category:    "workspace",
		Description: "Edits an existing event on Google Calendar by event ID.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Account alias or email"},
				"event_id": {"type": "string", "description": "Google Calendar event ID to modify"},
				"summary": {"type": "string", "description": "Updated event summary/title"},
				"start_time": {"type": "string", "description": "Updated ISO/RFC3339 start timestamp"},
				"duration_hours": {"type": "number", "description": "Updated duration in hours"},
				"description": {"type": "string", "description": "Updated notes or agenda"},
				"color": {"type": "string", "description": "Updated color name"}
			},
			"required": ["event_id"]
		}`,
		PromptUsageTip:     "Use calendar_edit_event to reschedule or update meetings.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "workspace:write",
	}
}

func (t *CalendarEditEventTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args CalendarEditEventArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	if strings.TrimSpace(args.EventID) == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "'event_id' cannot be empty"}, nil
	}

	patchPayload := make(map[string]any)
	if args.Summary != nil {
		patchPayload["summary"] = *args.Summary
	}
	if args.Description != nil {
		patchPayload["description"] = *args.Description
	}
	if args.Color != nil {
		patchPayload["colorId"] = resolveCalendarColorID(*args.Color)
	}

	if args.StartTime != nil {
		duration := 1.0
		if args.DurationHours != nil {
			duration = *args.DurationHours
		}
		startRFC, endRFC, err := parseEventTimestamps(*args.StartTime, duration)
		if err != nil {
			return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: err.Error()}, nil
		}
		patchPayload["start"] = map[string]string{"dateTime": startRFC}
		patchPayload["end"] = map[string]string{"dateTime": endRFC}
	}

	if len(patchPayload) == 0 {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "no fields provided to edit"}, nil
	}

	bodyBytes, _ := json.Marshal(patchPayload)
	endpoint := fmt.Sprintf("https://www.googleapis.com/calendar/v3/calendars/primary/events/%s", args.EventID)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodPatch, endpoint, bytes.NewReader(bodyBytes))
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to edit event: %v", err)}, nil
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Calendar API patch error (%d): %s", resp.StatusCode, string(respBody))}, nil
	}

	return &tools.ToolResult{Stdout: string(respBody)}, nil
}

// CalendarDeleteEventTool removes an event from Google Calendar.
type CalendarDeleteEventTool struct {
	client *GoogleClient
}

func NewCalendarDeleteEventTool(client *GoogleClient) *CalendarDeleteEventTool {
	return &CalendarDeleteEventTool{client: client}
}

func (t *CalendarDeleteEventTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "calendar_delete_event",
		Category:    "workspace",
		Description: "Permanently deletes an event from Google Calendar by event ID.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Account alias or email"},
				"event_id": {"type": "string", "description": "Google Calendar event ID to delete"}
			},
			"required": ["event_id"]
		}`,
		PromptUsageTip:     "Use calendar_delete_event when meetings or reminders are cancelled.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "workspace:write",
	}
}

func (t *CalendarDeleteEventTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args CalendarDeleteEventArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	if strings.TrimSpace(args.EventID) == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "'event_id' cannot be empty"}, nil
	}

	endpoint := fmt.Sprintf("https://www.googleapis.com/calendar/v3/calendars/primary/events/%s", args.EventID)
	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodDelete, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to delete event: %v", err)}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Calendar API delete error (%d): %s", resp.StatusCode, string(body))}, nil
	}

	return &tools.ToolResult{Stdout: fmt.Sprintf("Event %q successfully deleted.", args.EventID)}, nil
}

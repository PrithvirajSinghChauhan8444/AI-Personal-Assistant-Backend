package workspace

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"assistant/src/tools"
)

// TasksListArgs defines input parameters for listing tasks.
type TasksListArgs struct {
	Account   string `json:"account,omitempty"`
	TaskListID string `json:"task_list_id,omitempty"`
	Limit     int    `json:"limit,omitempty"`
}

// TasksCreateArgs defines input parameters for adding a new task.
type TasksCreateArgs struct {
	Account    string `json:"account,omitempty"`
	TaskListID string `json:"task_list_id,omitempty"`
	Title      string `json:"title"`
	Notes      string `json:"notes,omitempty"`
	Due        string `json:"due,omitempty"`
}

// TaskItem represents a single task entry.
type TaskItem struct {
	ID      string `json:"id"`
	Title   string `json:"title"`
	Status  string `json:"status"`
	Due     string `json:"due,omitempty"`
	Notes   string `json:"notes,omitempty"`
	Updated string `json:"updated,omitempty"`
}

// TasksListTool lists pending items from Google Tasks.
type TasksListTool struct {
	client *GoogleClient
}

func NewTasksListTool(client *GoogleClient) *TasksListTool {
	return &TasksListTool{client: client}
}

func (t *TasksListTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "tasks_list",
		Category:    "workspace",
		Description: "Lists pending items from the user's Google Tasks.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Complete email address of the account (e.g. 'user@example.com', 'work@company.com')"},
				"task_list_id": {"type": "string", "description": "Optional task list ID (defaults to '@default')"},
				"limit": {"type": "integer", "description": "Maximum tasks to return (default: 10)"}
			}
		}`,
		PromptUsageTip:     "Use tasks_list to check pending to-dos and action items.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *TasksListTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args TasksListArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	listID := args.TaskListID
	if listID == "" {
		listID = "@default"
	}

	limit := args.Limit
	if limit <= 0 {
		limit = 10
	} else if limit > 50 {
		limit = 50
	}

	endpoint := fmt.Sprintf("https://tasks.googleapis.com/tasks/v1/lists/%s/tasks?showCompleted=false&maxResults=%d",
		listID, limit)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to query Tasks API: %v", err)}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Tasks API error (%d): %s", resp.StatusCode, string(body))}, nil
	}

	var data struct {
		Items []struct {
			ID      string `json:"id"`
			Title   string `json:"title"`
			Status  string `json:"status"`
			Due     string `json:"due"`
			Notes   string `json:"notes"`
			Updated string `json:"updated"`
		} `json:"items"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to decode Tasks response: %v", err)}, nil
	}

	tasks := make([]TaskItem, 0, len(data.Items))
	for _, item := range data.Items {
		tasks = append(tasks, TaskItem{
			ID:      item.ID,
			Title:   item.Title,
			Status:  item.Status,
			Due:     item.Due,
			Notes:   item.Notes,
			Updated: item.Updated,
		})
	}

	resultBytes, _ := json.MarshalIndent(tasks, "", "  ")
	return &tools.ToolResult{Stdout: string(resultBytes)}, nil
}

// TasksCreateTool inserts a new to-do item into Google Tasks.
type TasksCreateTool struct {
	client *GoogleClient
}

func NewTasksCreateTool(client *GoogleClient) *TasksCreateTool {
	return &TasksCreateTool{client: client}
}

func (t *TasksCreateTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "tasks_create",
		Category:    "workspace",
		Description: "Creates a new to-do task item in Google Tasks.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Complete email address of the account (e.g. 'user@example.com', 'work@company.com')"},
				"task_list_id": {"type": "string", "description": "Optional task list ID (defaults to '@default')"},
				"title": {"type": "string", "description": "Title of the task"},
				"notes": {"type": "string", "description": "Optional task description or notes"},
				"due": {"type": "string", "description": "Optional RFC3339 due timestamp"}
			},
			"required": ["title"]
		}`,
		PromptUsageTip:     "Use tasks_create to record reminders, homework, and to-do items.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "workspace:write",
	}
}

func (t *TasksCreateTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args TasksCreateArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	if strings.TrimSpace(args.Title) == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "'title' cannot be empty"}, nil
	}

	listID := args.TaskListID
	if listID == "" {
		listID = "@default"
	}

	payload := map[string]string{
		"title": args.Title,
	}
	if args.Notes != "" {
		payload["notes"] = args.Notes
	}
	if args.Due != "" {
		payload["due"] = args.Due
	}

	bodyBytes, _ := json.Marshal(payload)
	endpoint := fmt.Sprintf("https://tasks.googleapis.com/tasks/v1/lists/%s/tasks", listID)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodPost, endpoint, bytes.NewReader(bodyBytes))
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to create task: %v", err)}, nil
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Tasks API error (%d): %s", resp.StatusCode, string(respBody))}, nil
	}

	return &tools.ToolResult{Stdout: string(respBody)}, nil
}

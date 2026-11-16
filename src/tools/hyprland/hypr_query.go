package hyprland

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"assistant/src/tools"
)

// --- 1. HyprGetActiveWindowTool ---

// HyprGetActiveWindowTool inspects the currently focused window in Hyprland.
type HyprGetActiveWindowTool struct{}

func NewHyprGetActiveWindowTool() *HyprGetActiveWindowTool {
	return &HyprGetActiveWindowTool{}
}

func (t *HyprGetActiveWindowTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "hypr_get_active_window",
		Category:           "hyprland",
		Description:        "Gets the currently active/focused window in Hyprland with its title, class, address, workspace, pid, floating status, position, and size in JSON.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use hypr_get_active_window to find out what application/window the user is currently working in.",
		Risk:               tools.RiskLow,
		RequiredCapability: "hyprland:read",
	}
}

func (t *HyprGetActiveWindowTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	out, err := executeHyprctl(ctx, "activewindow", "-j")
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to get active window: %v", err),
		}, nil
	}
	return &tools.ToolResult{Stdout: out}, nil
}

// --- 2. HyprGetWorkspacesTool ---

// HyprGetWorkspacesTool lists all active workspaces across monitors.
type HyprGetWorkspacesTool struct{}

func NewHyprGetWorkspacesTool() *HyprGetWorkspacesTool {
	return &HyprGetWorkspacesTool{}
}

func (t *HyprGetWorkspacesTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "hypr_get_workspaces",
		Category:           "hyprland",
		Description:        "Lists all active workspaces with their IDs, names, assigned monitors, window counts, and properties in JSON.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use hypr_get_workspaces to inspect workspace allocation, monitor assignments, and window distribution.",
		Risk:               tools.RiskLow,
		RequiredCapability: "hyprland:read",
	}
}

func (t *HyprGetWorkspacesTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	out, err := executeHyprctl(ctx, "workspaces", "-j")
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to get workspaces: %v", err),
		}, nil
	}
	return &tools.ToolResult{Stdout: out}, nil
}

// --- 3. HyprGetClientsTool ---

// HyprGetClientsArgs defines optional filtering parameters.
type HyprGetClientsArgs struct {
	Workspace string `json:"workspace"`
	ClassName string `json:"class_name"`
	Title     string `json:"title"`
}

// HyprGetClientsTool lists open application windows across all workspaces with filtering.
type HyprGetClientsTool struct{}

func NewHyprGetClientsTool() *HyprGetClientsTool {
	return &HyprGetClientsTool{}
}

func (t *HyprGetClientsTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_get_clients",
		Category:    "hyprland",
		Description: "Lists all open client windows across all workspaces in Hyprland with optional filtering by workspace, window class, or title.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"workspace": {"type": "string", "description": "Optional filter by workspace name or ID (e.g. '1', '3', 'special:scratchpad')"},
				"class_name": {"type": "string", "description": "Optional case-insensitive filter by window class (e.g. 'firefox', 'code', 'kitty')"},
				"title": {"type": "string", "description": "Optional case-insensitive substring filter by window title"}
			}
		}`,
		PromptUsageTip:     "Use hypr_get_clients to find window addresses or locate where specific applications are open.",
		Risk:               tools.RiskLow,
		RequiredCapability: "hyprland:read",
	}
}

func (t *HyprGetClientsTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprGetClientsArgs
	if strings.TrimSpace(argsJSON) != "" && argsJSON != "{}" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	out, err := executeHyprctl(ctx, "clients", "-j")
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to get clients: %v", err),
		}, nil
	}

	// If no filter requested, return raw JSON directly
	if args.Workspace == "" && args.ClassName == "" && args.Title == "" {
		return &tools.ToolResult{Stdout: out}, nil
	}

	var rawClients []map[string]interface{}
	if err := json.Unmarshal([]byte(out), &rawClients); err != nil {
		return &tools.ToolResult{Stdout: out}, nil
	}

	var filtered []map[string]interface{}
	filterClass := strings.ToLower(strings.TrimSpace(args.ClassName))
	filterTitle := strings.ToLower(strings.TrimSpace(args.Title))
	filterWs := strings.TrimSpace(args.Workspace)

	for _, client := range rawClients {
		if filterClass != "" {
			cClass, _ := client["class"].(string)
			if !strings.Contains(strings.ToLower(cClass), filterClass) {
				continue
			}
		}
		if filterTitle != "" {
			cTitle, _ := client["title"].(string)
			if !strings.Contains(strings.ToLower(cTitle), filterTitle) {
				continue
			}
		}
		if filterWs != "" {
			wsObj, ok := client["workspace"].(map[string]interface{})
			if ok {
				wsName, _ := wsObj["name"].(string)
				wsID := fmt.Sprintf("%v", wsObj["id"])
				if wsName != filterWs && wsID != filterWs {
					continue
				}
			}
		}
		filtered = append(filtered, client)
	}

	filteredJSON, err := json.MarshalIndent(filtered, "", "  ")
	if err != nil {
		return &tools.ToolResult{Stdout: out}, nil
	}
	return &tools.ToolResult{Stdout: string(filteredJSON)}, nil
}

// --- 4. HyprGetMonitorsTool ---

// HyprGetMonitorsTool lists connected outputs and their configurations.
type HyprGetMonitorsTool struct{}

func NewHyprGetMonitorsTool() *HyprGetMonitorsTool {
	return &HyprGetMonitorsTool{}
}

func (t *HyprGetMonitorsTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "hypr_get_monitors",
		Category:           "hyprland",
		Description:        "Lists all connected monitors/displays, their resolutions, refresh rates, active workspaces, and focus states in JSON.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use hypr_get_monitors to inspect multi-monitor setups and display geometry.",
		Risk:               tools.RiskLow,
		RequiredCapability: "hyprland:read",
	}
}

func (t *HyprGetMonitorsTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	out, err := executeHyprctl(ctx, "monitors", "-j")
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to get monitors: %v", err),
		}, nil
	}
	return &tools.ToolResult{Stdout: out}, nil
}

package hyprland

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"assistant/src/tools"
)

// --- 5. HyprDispatchTool ---

type HyprDispatchArgs struct {
	Dispatcher string `json:"dispatcher"`
	Args       string `json:"args"`
}

type HyprDispatchTool struct{}

func NewHyprDispatchTool() *HyprDispatchTool {
	return &HyprDispatchTool{}
}

func (t *HyprDispatchTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_dispatch",
		Category:    "hyprland",
		Description: "Executes a keybind dispatcher or command through hyprctl dispatch with arguments (supports classic dispatchers and Lua expressions).",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"dispatcher": {"type": "string", "description": "Dispatcher name (e.g. 'workspace', 'focuswindow', 'togglefloating', 'exec') or Lua expression ('hl.dsp.window.float()')"},
				"args": {"type": "string", "description": "Arguments for the dispatcher (e.g. '1', 'firefox', 'l')"}
			},
			"required": ["dispatcher"]
		}`,
		PromptUsageTip:     "Use hypr_dispatch for any custom or raw Hyprland window manager dispatching actions.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "hyprland:dispatch",
	}
}

func (t *HyprDispatchTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprDispatchArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments: %v", err),
		}, nil
	}

	if strings.TrimSpace(args.Dispatcher) == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "missing required field: dispatcher",
		}, nil
	}

	return executeHyprDispatch(ctx, args.Dispatcher, args.Args)
}

// --- 6. HyprSwitchWorkspaceTool ---

type HyprSwitchWorkspaceArgs struct {
	Workspace string `json:"workspace"`
}

type HyprSwitchWorkspaceTool struct{}

func NewHyprSwitchWorkspaceTool() *HyprSwitchWorkspaceTool {
	return &HyprSwitchWorkspaceTool{}
}

func (t *HyprSwitchWorkspaceTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_switch_workspace",
		Category:    "hyprland",
		Description: "Switches the active workspace on the current monitor to a target workspace (by ID, name, or relative offset like '+1', '-1', 'special:scratchpad').",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"workspace": {"type": "string", "description": "Target workspace (e.g. '1', '2', 'work', '+1', '-1', 'special:scratchpad')"}
			},
			"required": ["workspace"]
		}`,
		PromptUsageTip:     "Use hypr_switch_workspace when asked to navigate or switch to another desktop workspace.",
		Risk:               tools.RiskLow,
		RequiredCapability: "hyprland:workspace",
	}
}

func (t *HyprSwitchWorkspaceTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprSwitchWorkspaceArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments: %v", err),
		}, nil
	}

	target := strings.TrimSpace(args.Workspace)
	if target == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "missing required field: workspace",
		}, nil
	}

	return executeHyprDispatch(ctx, "workspace", target)
}

// --- 7. HyprMoveWindowTool ---

type HyprMoveWindowArgs struct {
	Workspace string `json:"workspace"`
	Direction string `json:"direction"`
	Silent    bool   `json:"silent"`
	Window    string `json:"window"`
}

type HyprMoveWindowTool struct{}

func NewHyprMoveWindowTool() *HyprMoveWindowTool {
	return &HyprMoveWindowTool{}
}

func (t *HyprMoveWindowTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_move_window",
		Category:    "hyprland",
		Description: "Moves a window to a target workspace or in a direction (l/r/u/d), with optional silent mode.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"workspace": {"type": "string", "description": "Target workspace ID or name (e.g. '3', 'special:scratchpad')"},
				"direction": {"type": "string", "description": "Direction to move window within layout: 'l', 'r', 'u', 'd'"},
				"silent": {"type": "boolean", "description": "Whether to move silently without following focus (default: false)"},
				"window": {"type": "string", "description": "Target window address or class regex (default: currently active window)"}
			}
		}`,
		PromptUsageTip:     "Use hypr_move_window to move an application to another workspace or reposition it in the layout.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "hyprland:window",
	}
}

func (t *HyprMoveWindowTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprMoveWindowArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments: %v", err),
		}, nil
	}

	if args.Workspace != "" {
		disp := "movetoworkspace"
		if args.Silent {
			disp = "movetoworkspacesilent"
		}
		target := args.Workspace
		if args.Window != "" {
			target = fmt.Sprintf("%s,%s", args.Workspace, args.Window)
		}
		return executeHyprDispatch(ctx, disp, target)
	}

	if args.Direction != "" {
		dir := strings.ToLower(strings.TrimSpace(args.Direction))
		return executeHyprDispatch(ctx, "movewindow", dir)
	}

	return &tools.ToolResult{
		IsError:  true,
		ExitCode: 1,
		Stderr:   "either workspace or direction must be specified",
	}, nil
}

// --- 8. HyprFocusWindowTool ---

type HyprFocusWindowArgs struct {
	Window string `json:"window"`
}

type HyprFocusWindowTool struct{}

func NewHyprFocusWindowTool() *HyprFocusWindowTool {
	return &HyprFocusWindowTool{}
}

func (t *HyprFocusWindowTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_focus_window",
		Category:    "hyprland",
		Description: "Focuses a specific window by class, title regex, or address.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"window": {"type": "string", "description": "Window title, class regex, or address (e.g. 'firefox', 'code', 'address:0x...')"}
			},
			"required": ["window"]
		}`,
		PromptUsageTip:     "Use hypr_focus_window to switch focus to a specific opened application.",
		Risk:               tools.RiskLow,
		RequiredCapability: "hyprland:window",
	}
}

func (t *HyprFocusWindowTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprFocusWindowArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments: %v", err),
		}, nil
	}

	target := strings.TrimSpace(args.Window)
	if target == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "missing required field: window",
		}, nil
	}

	return executeHyprDispatch(ctx, "focuswindow", target)
}

// --- 9. HyprWindowActionTool ---

type HyprWindowActionArgs struct {
	Action string `json:"action"`
	Window string `json:"window"`
}

type HyprWindowActionTool struct{}

func NewHyprWindowActionTool() *HyprWindowActionTool {
	return &HyprWindowActionTool{}
}

func (t *HyprWindowActionTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_window_action",
		Category:    "hyprland",
		Description: "Performs layout and state actions on a window: toggle floating, fullscreen, pin, center, or move focus.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"action": {
					"type": "string",
					"description": "Action to perform: 'togglefloating', 'fullscreen', 'pin', 'center', 'cyclenext', 'movefocus_l', 'movefocus_r', 'movefocus_u', 'movefocus_d'",
					"enum": ["togglefloating", "fullscreen", "pin", "center", "cyclenext", "movefocus_l", "movefocus_r", "movefocus_u", "movefocus_d"]
				},
				"window": {"type": "string", "description": "Optional target window address or class regex (default: active window)"}
			},
			"required": ["action"]
		}`,
		PromptUsageTip:     "Use hypr_window_action to float, fullscreen, pin, or navigate windows.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "hyprland:window",
	}
}

func (t *HyprWindowActionTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprWindowActionArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments: %v", err),
		}, nil
	}

	action := strings.ToLower(strings.TrimSpace(args.Action))
	switch action {
	case "togglefloating":
		return executeHyprDispatch(ctx, "togglefloating", args.Window)
	case "fullscreen":
		return executeHyprDispatch(ctx, "fullscreen", "0")
	case "pin":
		return executeHyprDispatch(ctx, "pin", args.Window)
	case "center":
		return executeHyprDispatch(ctx, "centerwindow", "")
	case "cyclenext":
		return executeHyprDispatch(ctx, "cyclenext", "")
	case "movefocus_l":
		return executeHyprDispatch(ctx, "movefocus", "l")
	case "movefocus_r":
		return executeHyprDispatch(ctx, "movefocus", "r")
	case "movefocus_u":
		return executeHyprDispatch(ctx, "movefocus", "u")
	case "movefocus_d":
		return executeHyprDispatch(ctx, "movefocus", "d")
	default:
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("unsupported action: %s", action),
		}, nil
	}
}

// --- 10. HyprCloseWindowTool ---

type HyprCloseWindowArgs struct {
	Window string `json:"window"`
}

type HyprCloseWindowTool struct{}

func NewHyprCloseWindowTool() *HyprCloseWindowTool {
	return &HyprCloseWindowTool{}
}

func (t *HyprCloseWindowTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_close_window",
		Category:    "hyprland",
		Description: "Gracefully closes the active window or a specified window in Hyprland.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"window": {"type": "string", "description": "Target window address or class regex (if omitted, closes the currently focused window)"}
			}
		}`,
		PromptUsageTip:     "Use with care. Closes the active window or target window. Confirm with user before closing working windows.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "hyprland:window",
	}
}

func (t *HyprCloseWindowTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprCloseWindowArgs
	if strings.TrimSpace(argsJSON) != "" && argsJSON != "{}" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	target := strings.TrimSpace(args.Window)
	if target == "" {
		return executeHyprDispatch(ctx, "killactive", "")
	}
	return executeHyprDispatch(ctx, "closewindow", target)
}

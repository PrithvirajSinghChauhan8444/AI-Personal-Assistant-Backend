package hyprland

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"

	"assistant/src/tools"
)

// --- 11. HyprNotifyTool ---

type HyprNotifyArgs struct {
	Message string `json:"message"`
	Icon    int    `json:"icon"`
	TimeMs  int    `json:"time_ms"`
	Color   string `json:"color"`
}

type HyprNotifyTool struct{}

func NewHyprNotifyTool() *HyprNotifyTool {
	return &HyprNotifyTool{}
}

func (t *HyprNotifyTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_notify",
		Category:    "hyprland",
		Description: "Sends a desktop notification directly through Hyprland's built-in notification system.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"message": {"type": "string", "description": "Notification message to display"},
				"icon": {"type": "integer", "description": "Icon type: 0=Warning, 1=Info, 2=Hint, 3=Error, 4=Confused, 5=Ok, -1=None (default: 1)", "default": 1},
				"time_ms": {"type": "integer", "description": "Display duration in milliseconds (default: 3000)", "default": 3000},
				"color": {"type": "string", "description": "Notification color format (default: '0')", "default": "0"}
			},
			"required": ["message"]
		}`,
		PromptUsageTip:     "Use hypr_notify to alert the user of finished tasks or important status updates via on-screen notification.",
		Risk:               tools.RiskLow,
		RequiredCapability: "hyprland:system",
	}
}

func (t *HyprNotifyTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprNotifyArgs
	// defaults
	args.Icon = 1
	args.TimeMs = 3000
	args.Color = "0"

	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments: %v", err),
		}, nil
	}

	if strings.TrimSpace(args.Message) == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "missing required field: message",
		}, nil
	}

	if args.TimeMs <= 0 {
		args.TimeMs = 3000
	}
	if args.Color == "" {
		args.Color = "0"
	}

	iconStr := strconv.Itoa(args.Icon)
	timeStr := strconv.Itoa(args.TimeMs)

	out, err := executeHyprctl(ctx, "notify", iconStr, timeStr, args.Color, args.Message)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to send notification: %v", err),
		}, nil
	}

	return &tools.ToolResult{Stdout: fmt.Sprintf("Notification sent: %s", out)}, nil
}

// --- 12. HyprKeywordTool ---

type HyprKeywordArgs struct {
	Keyword string `json:"keyword"`
	Value   string `json:"value"`
}

type HyprKeywordTool struct{}

func NewHyprKeywordTool() *HyprKeywordTool {
	return &HyprKeywordTool{}
}

func (t *HyprKeywordTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "hypr_keyword",
		Category:    "hyprland",
		Description: "Sets a dynamic Hyprland config keyword (e.g. 'general:border_size 2') or forces a reload of the Hyprland configuration.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"keyword": {"type": "string", "description": "Keyword/setting name (e.g. 'general:border_size', 'animations:enabled', or 'reload')"},
				"value": {"type": "string", "description": "Value to set (if keyword is 'reload' or value is omitted, triggers config reload)"}
			},
			"required": ["keyword"]
		}`,
		PromptUsageTip:     "Use hypr_keyword to tweak compositor visual settings dynamically or reload compositor rules.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "hyprland:config",
	}
}

func (t *HyprKeywordTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args HyprKeywordArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments: %v", err),
		}, nil
	}

	keyword := strings.TrimSpace(args.Keyword)
	if keyword == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "missing required field: keyword",
		}, nil
	}

	// If reload requested
	if strings.ToLower(keyword) == "reload" || (args.Value == "" && strings.Contains(strings.ToLower(keyword), "reload")) {
		out, err := executeHyprctl(ctx, "reload", "config-only")
		if err != nil {
			return &tools.ToolResult{
				IsError:  true,
				ExitCode: 1,
				Stderr:   fmt.Sprintf("hyprctl reload failed: %v", err),
			}, nil
		}
		return &tools.ToolResult{Stdout: fmt.Sprintf("Hyprland config reloaded: %s", out)}, nil
	}

	// Check if in Lua environment
	if isLuaConfigProvider(ctx) {
		// In Lua mode, hyprctl eval 'hl.config({ ... })' can set config table
		if strings.Contains(keyword, ":") {
			parts := strings.SplitN(keyword, ":", 2)
			section := strings.TrimSpace(parts[0])
			opt := strings.TrimSpace(parts[1])
			val := strings.TrimSpace(args.Value)

			// Determine numeric vs string
			var valExpr string
			if _, err := strconv.ParseFloat(val, 64); err == nil {
				valExpr = val
			} else if val == "true" || val == "false" {
				valExpr = val
			} else {
				valExpr = fmt.Sprintf("%q", val)
			}

			luaExpr := fmt.Sprintf("hl.config({ %s = { %s = %s } })", section, opt, valExpr)
			out, err := executeHyprctl(ctx, "eval", luaExpr)
			if err == nil {
				return &tools.ToolResult{Stdout: fmt.Sprintf("Hyprland Lua config updated: %s", out)}, nil
			}
		}
	}

	// Classic hyprctl keyword command
	out, err := executeHyprctl(ctx, "keyword", keyword, args.Value)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("hyprctl keyword failed: %v", err),
		}, nil
	}

	return &tools.ToolResult{Stdout: fmt.Sprintf("Hyprland keyword updated: %s", out)}, nil
}

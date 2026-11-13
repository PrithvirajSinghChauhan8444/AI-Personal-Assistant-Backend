package sys

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"

	"assistant/src/tools"
)

// SysBrightnessSetArgs defines arguments for setting brightness.
type SysBrightnessSetArgs struct {
	Level int `json:"level"`
}

// SysBrightnessGetTool retrieves current screen brightness percentage.
type SysBrightnessGetTool struct{}

func NewSysBrightnessGetTool() *SysBrightnessGetTool {
	return &SysBrightnessGetTool{}
}

func (t *SysBrightnessGetTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_brightness_get",
		Category:           "system",
		Description:        "Gets the current screen brightness percentage.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use sys_brightness_get to check display backlight level.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysBrightnessGetTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	currOut, err := executeCommand(ctx, "brightnessctl", "g")
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to get brightness: %v", err),
		}, nil
	}

	maxOut, err := executeCommand(ctx, "brightnessctl", "m")
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to get max brightness: %v", err),
		}, nil
	}

	curr, err1 := strconv.ParseFloat(strings.TrimSpace(currOut), 64)
	max, err2 := strconv.ParseFloat(strings.TrimSpace(maxOut), 64)
	if err1 != nil || err2 != nil || max <= 0 {
		return &tools.ToolResult{Stdout: fmt.Sprintf("Brightness raw: %s / %s", currOut, maxOut)}, nil
	}

	percent := int((curr / max) * 100.0)
	return &tools.ToolResult{Stdout: fmt.Sprintf("Screen Brightness: %d%%", percent)}, nil
}

// SysBrightnessSetTool adjusts screen brightness percentage.
type SysBrightnessSetTool struct{}

func NewSysBrightnessSetTool() *SysBrightnessSetTool {
	return &SysBrightnessSetTool{}
}

func (t *SysBrightnessSetTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "sys_brightness_set",
		Category:    "system",
		Description: "Sets the screen brightness to a specific percentage (1-100).",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"level": {"type": "integer", "description": "Target brightness percentage (1 to 100)"}
			},
			"required": ["level"]
		}`,
		PromptUsageTip:     "Use sys_brightness_set to adjust backlight.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysBrightnessSetTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysBrightnessSetArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	if args.Level < 1 {
		args.Level = 1
	} else if args.Level > 100 {
		args.Level = 100
	}

	target := fmt.Sprintf("%d%%", args.Level)
	out, err := executeCommand(ctx, "brightnessctl", "s", target)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to set brightness: %v", err),
		}, nil
	}

	return &tools.ToolResult{Stdout: fmt.Sprintf("Screen brightness set to %s (%s)", target, out)}, nil
}

package sys

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"time"

	"assistant/src/tools"
)

// SysVolumeSetArgs defines arguments for setting volume.
type SysVolumeSetArgs struct {
	Level int `json:"level"`
}

// executeCommand runs a command with a strict timeout and returns stdout or error.
func executeCommand(ctx context.Context, name string, args ...string) (string, error) {
	cmdCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	cmd := exec.CommandContext(cmdCtx, name, args...)
	out, err := cmd.CombinedOutput()
	outputStr := strings.TrimSpace(string(out))
	if err != nil {
		return outputStr, fmt.Errorf("%s failed: %w (output: %s)", name, err, outputStr)
	}
	return outputStr, nil
}

// SysVolumeGetTool retrieves current audio volume and mute status.
type SysVolumeGetTool struct{}

func NewSysVolumeGetTool() *SysVolumeGetTool {
	return &SysVolumeGetTool{}
}

func (t *SysVolumeGetTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_volume_get",
		Category:           "system",
		Description:        "Gets the current system audio volume percentage and mute status.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use sys_volume_get to inspect sound levels.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysVolumeGetTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	// Try pamixer first
	if out, err := executeCommand(ctx, "pamixer", "--get-volume"); err == nil {
		muteOut, _ := executeCommand(ctx, "pamixer", "--get-mute")
		isMuted := strings.TrimSpace(muteOut) == "true"
		muteStatus := "unmuted"
		if isMuted {
			muteStatus = "muted"
		}
		return &tools.ToolResult{Stdout: fmt.Sprintf("Volume: %s%% (%s)", out, muteStatus)}, nil
	}

	// Fallback to amixer
	if out, err := executeCommand(ctx, "amixer", "sget", "Master"); err == nil {
		re := regexp.MustCompile(`\[(\d+)%\]`)
		matches := re.FindStringSubmatch(out)
		if len(matches) > 1 {
			return &tools.ToolResult{Stdout: fmt.Sprintf("Volume: %s%%", matches[1])}, nil
		}
	}

	return &tools.ToolResult{
		IsError:  true,
		ExitCode: 1,
		Stderr:   "unable to determine volume (neither pamixer nor amixer succeeded)",
	}, nil
}

// SysVolumeSetTool sets system audio volume.
type SysVolumeSetTool struct{}

func NewSysVolumeSetTool() *SysVolumeSetTool {
	return &SysVolumeSetTool{}
}

func (t *SysVolumeSetTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "sys_volume_set",
		Category:    "system",
		Description: "Sets the system audio volume to a specific percentage (0-100).",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"level": {"type": "integer", "description": "Target volume percentage (0 to 100)"}
			},
			"required": ["level"]
		}`,
		PromptUsageTip:     "Use sys_volume_set to adjust speaker output level.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysVolumeSetTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysVolumeSetArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	if args.Level < 0 {
		args.Level = 0
	} else if args.Level > 100 {
		args.Level = 100
	}

	levelStr := strconv.Itoa(args.Level)

	// Try pamixer
	if _, err := executeCommand(ctx, "pamixer", "--set-volume", levelStr); err == nil {
		return &tools.ToolResult{Stdout: fmt.Sprintf("Volume set to %d%% via pamixer", args.Level)}, nil
	}

	// Fallback to amixer
	if _, err := executeCommand(ctx, "amixer", "sset", "Master", levelStr+"%"); err == nil {
		return &tools.ToolResult{Stdout: fmt.Sprintf("Volume set to %d%% via amixer", args.Level)}, nil
	}

	return &tools.ToolResult{
		IsError:  true,
		ExitCode: 1,
		Stderr:   "failed to set volume (neither pamixer nor amixer available)",
	}, nil
}

// SysVolumeMuteTool toggles audio mute status.
type SysVolumeMuteTool struct{}

func NewSysVolumeMuteTool() *SysVolumeMuteTool {
	return &SysVolumeMuteTool{}
}

func (t *SysVolumeMuteTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_volume_mute",
		Category:           "system",
		Description:        "Toggles system audio mute state on or off.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use sys_volume_mute to quickly silence or unsilence speakers.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysVolumeMuteTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	// Try pamixer
	if _, err := executeCommand(ctx, "pamixer", "--toggle-mute"); err == nil {
		muteOut, _ := executeCommand(ctx, "pamixer", "--get-mute")
		isMuted := strings.TrimSpace(muteOut) == "true"
		state := "unmuted"
		if isMuted {
			state = "muted"
		}
		return &tools.ToolResult{Stdout: fmt.Sprintf("Audio is now %s", state)}, nil
	}

	// Fallback to amixer
	if _, err := executeCommand(ctx, "amixer", "sset", "Master", "toggle"); err == nil {
		return &tools.ToolResult{Stdout: "Toggled audio mute state via amixer"}, nil
	}

	return &tools.ToolResult{
		IsError:  true,
		ExitCode: 1,
		Stderr:   "failed to toggle mute (neither pamixer nor amixer available)",
	}, nil
}

package sys

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
	"time"

	"assistant/src/tools"
)

// SysLaunchAppArgs defines arguments to launch an application.
type SysLaunchAppArgs struct {
	AppName   string   `json:"app_name"`
	Arguments []string `json:"arguments,omitempty"`
}

// SysLaunchAppTool launches an application or folder detached.
type SysLaunchAppTool struct{}

func NewSysLaunchAppTool() *SysLaunchAppTool {
	return &SysLaunchAppTool{}
}

func (t *SysLaunchAppTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "sys_launch_app",
		Category:    "system",
		Description: "Launches an application, URI, or directory path detached on the desktop session.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"app_name": {"type": "string", "description": "Application name or path (e.g. 'code', 'firefox', 'vlc', or directory)"},
				"arguments": {
					"type": "array",
					"items": {"type": "string"},
					"description": "Optional CLI arguments or file targets"
				}
			},
			"required": ["app_name"]
		}`,
		PromptUsageTip:     "Use sys_launch_app to open desktop software or folders without blocking execution turns.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysLaunchAppTool) Execute(_ context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysLaunchAppArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	appName := strings.TrimSpace(args.AppName)
	if appName == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "'app_name' cannot be empty"}, nil
	}

	// If appName is a directory or URL, use xdg-open
	if strings.HasPrefix(appName, "/") || strings.HasPrefix(appName, "http://") || strings.HasPrefix(appName, "https://") {
		cmd := exec.Command("xdg-open", appName)
		if err := cmd.Start(); err != nil {
			return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to open with xdg-open: %v", err)}, nil
		}
		return &tools.ToolResult{Stdout: fmt.Sprintf("Launched %q via xdg-open (PID %d)", appName, cmd.Process.Pid)}, nil
	}

	// Look up binary
	targetBin, err := exec.LookPath(appName)
	if err != nil {
		// Fallback to xdg-open
		cmd := exec.Command("xdg-open", appName)
		if startErr := cmd.Start(); startErr == nil {
			return &tools.ToolResult{Stdout: fmt.Sprintf("Launched %q via xdg-open fallback (PID %d)", appName, cmd.Process.Pid)}, nil
		}
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("application %q not found in PATH: %v", appName, err),
		}, nil
	}

	cmd := exec.Command(targetBin, args.Arguments...)
	if err := cmd.Start(); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to start application %q: %v", targetBin, err),
		}, nil
	}

	return &tools.ToolResult{Stdout: fmt.Sprintf("Launched application %q successfully (PID %d)", targetBin, cmd.Process.Pid)}, nil
}

// SysGetTimeTool provides current time and date in both local and UTC.
type SysGetTimeTool struct{}

func NewSysGetTimeTool() *SysGetTimeTool {
	return &SysGetTimeTool{}
}

func (t *SysGetTimeTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_get_time",
		Category:           "system",
		Description:        "Returns the current system timestamp in both local time and UTC.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use sys_get_time to check the exact date, time, weekday, or timezone.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysGetTimeTool) Execute(_ context.Context, _ string) (*tools.ToolResult, error) {
	nowLocal := time.Now()
	nowUTC := nowLocal.UTC()
	zone, offset := nowLocal.Zone()
	offsetHours := float64(offset) / 3600.0

	timeInfo := map[string]any{
		"local_formatted": nowLocal.Format("03:04 PM, Monday 02 January 2006"),
		"local_rfc3339":   nowLocal.Format(time.RFC3339),
		"utc_formatted":   nowUTC.Format("2006-01-02 15:04:05 UTC"),
		"utc_rfc3339":     nowUTC.Format(time.RFC3339),
		"weekday":         nowLocal.Weekday().String(),
		"timezone":        zone,
		"utc_offset":      fmt.Sprintf("%+.1f hours", offsetHours),
	}

	resBytes, _ := json.MarshalIndent(timeInfo, "", "  ")
	return &tools.ToolResult{Stdout: string(resBytes)}, nil
}

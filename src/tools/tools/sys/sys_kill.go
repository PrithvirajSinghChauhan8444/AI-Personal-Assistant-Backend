package sys

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"syscall"

	"assistant/src/tools"
)

type SysKillArgs struct {
	PID    int    `json:"pid"`
	Signal string `json:"signal,omitempty"`
}

type SysKillTool struct{}

func NewSysKillTool() *SysKillTool {
	return &SysKillTool{}
}

func (t *SysKillTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_kill",
		Category:           "system",
		Description:        "Terminates a process by PID with a specified signal (SIGTERM, SIGKILL, SIGHUP, SIGINT).",
		ParameterSchema:    `{"type":"object","properties":{"pid":{"type":"integer","description":"Process ID to terminate"},"signal":{"type":"string","description":"Signal name: SIGTERM, SIGKILL, SIGHUP, SIGINT (default: SIGTERM)","default":"SIGTERM"}},"required":["pid"]}`,
		PromptUsageTip:     "Use sys_kill to stop runaway processes. Attempt graceful SIGTERM before forceful SIGKILL.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "sys:admin",
	}
}

func (t *SysKillTool) Execute(_ context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysKillArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for sys_kill: %v", err),
		}, nil
	}

	if args.PID <= 1 {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("refusing to signal PID %d (system protected process)", args.PID),
		}, nil
	}

	sig := resolveSignal(args.Signal)

	proc, err := os.FindProcess(args.PID)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to find process with PID %d: %v", args.PID, err),
		}, nil
	}

	if err := proc.Signal(sig); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to send signal to PID %d: %v", args.PID, err),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   fmt.Sprintf("successfully sent signal %v to process %d", sig, args.PID),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func resolveSignal(sigName string) syscall.Signal {
	switch strings.ToUpper(strings.TrimSpace(sigName)) {
	case "SIGKILL", "KILL", "9":
		return syscall.SIGKILL
	case "SIGHUP", "HUP", "1":
		return syscall.SIGHUP
	case "SIGINT", "INT", "2":
		return syscall.SIGINT
	default:
		return syscall.SIGTERM
	}
}

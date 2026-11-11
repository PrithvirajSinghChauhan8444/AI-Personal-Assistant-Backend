package sys

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"time"

	"assistant/src/tools"
)

type SysExecArgs struct {
	Command        string `json:"command"`
	TimeoutSeconds int    `json:"timeout_seconds,omitempty"`
	Cwd            string `json:"cwd,omitempty"`
}

type SysExecTool struct{}

func NewSysExecTool() *SysExecTool {
	return &SysExecTool{}
}

func (t *SysExecTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_exec",
		Category:           "system",
		Description:        "Executes an isolated Linux bash or shell command with a timeout deadline.",
		ParameterSchema:    `{"type":"object","properties":{"command":{"type":"string","description":"Bash or shell command to execute"},"timeout_seconds":{"type":"integer","description":"Command timeout deadline in seconds (default: 30)","default":30},"cwd":{"type":"string","description":"Working directory for the process"}},"required":["command"]}`,
		PromptUsageTip:     "Use sys_exec for terminal commands, compiling, and running scripts. Specify cwd when executing within specific projects.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "sys:exec",
	}
}

func (t *SysExecTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysExecArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for sys_exec: %v", err),
		}, nil
	}

	if args.Command == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "command cannot be empty",
		}, nil
	}

	timeoutSec := args.TimeoutSeconds
	if timeoutSec <= 0 {
		timeoutSec = 30
	} else if timeoutSec > 300 {
		timeoutSec = 300
	}

	execCtx, cancel := context.WithTimeout(ctx, time.Duration(timeoutSec)*time.Second)
	defer cancel()

	shell := "/bin/bash"
	if _, err := exec.LookPath(shell); err != nil {
		shell = "/bin/sh"
	}

	cmd := exec.CommandContext(execCtx, shell, "-c", args.Command)
	if args.Cwd != "" {
		cmd.Dir = args.Cwd
	}

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	exitCode := 0
	isError := false

	if err != nil {
		isError = true
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			exitCode = 1
			if stderrBuf.Len() == 0 {
				stderrBuf.WriteString(err.Error())
			}
		}
	}

	return &tools.ToolResult{
		Stdout:   stdoutBuf.String(),
		Stderr:   stderrBuf.String(),
		ExitCode: exitCode,
		IsError:  isError,
	}, nil
}

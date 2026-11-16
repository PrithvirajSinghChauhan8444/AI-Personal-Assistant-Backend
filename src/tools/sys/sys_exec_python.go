package sys

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
	"time"

	"assistant/src/tools"
)

// SysExecPythonArgs defines arguments for executing Python code.
type SysExecPythonArgs struct {
	Code           string `json:"code"`
	TimeoutSeconds int    `json:"timeout_seconds,omitempty"`
}

// SysExecPythonTool executes Python code in an isolated subshell.
type SysExecPythonTool struct{}

func NewSysExecPythonTool() *SysExecPythonTool {
	return &SysExecPythonTool{}
}

func (t *SysExecPythonTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "sys_exec_python",
		Category:    "system",
		Description: "Executes an ephemeral Python script safely in a subprocess and returns stdout/stderr.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"code": {"type": "string", "description": "Python source code to execute"},
				"timeout_seconds": {"type": "integer", "description": "Timeout in seconds (default: 30)", "default": 30}
			},
			"required": ["code"]
		}`,
		PromptUsageTip:     "Use sys_exec_python for mathematical computation, data processing, or rapid verification.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "system:exec",
	}
}

func (t *SysExecPythonTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysExecPythonArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	code := strings.TrimSpace(args.Code)
	if code == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "'code' cannot be empty"}, nil
	}

	timeoutSec := args.TimeoutSeconds
	if timeoutSec <= 0 {
		timeoutSec = 30
	} else if timeoutSec > 120 {
		timeoutSec = 120
	}

	cmdCtx, cancel := context.WithTimeout(ctx, time.Duration(timeoutSec)*time.Second)
	defer cancel()

	// Locate python3 or python executable
	pythonBin := "python3"
	if _, err := exec.LookPath(pythonBin); err != nil {
		pythonBin = "python"
	}

	cmd := exec.CommandContext(cmdCtx, pythonBin, "-c", code)
	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	stdoutStr := strings.TrimSpace(stdoutBuf.String())
	stderrStr := strings.TrimSpace(stderrBuf.String())

	if err != nil {
		exitCode := 1
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		}
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: exitCode,
			Stdout:   stdoutStr,
			Stderr:   fmt.Sprintf("%v: %s", err, stderrStr),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   stdoutStr,
		Stderr:   stderrStr,
		ExitCode: 0,
	}, nil
}

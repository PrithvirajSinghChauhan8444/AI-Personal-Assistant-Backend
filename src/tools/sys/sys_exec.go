package sys

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"assistant/src/tools"
)

type SysExecArgs struct {
	Command        string `json:"command"`
	TimeoutSeconds int    `json:"timeout_seconds,omitempty"`
	Cwd            string `json:"cwd,omitempty"`
	Background     bool   `json:"background,omitempty"`
	LogFile        string `json:"log_file,omitempty"`
}

type SysExecTool struct{}

func NewSysExecTool() *SysExecTool {
	return &SysExecTool{}
}

func (t *SysExecTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:     "sys_exec",
		Category: "system",
		Description: "Executes a Linux bash or shell command with a timeout deadline, or launches background/GUI processes detached.",
		ParameterSchema: `{"type":"object","properties":{"command":{"type":"string","description":"Bash or shell command to execute"},"timeout_seconds":{"type":"integer","description":"Command timeout deadline in seconds (default: 30)","default":30},"cwd":{"type":"string","description":"Working directory for the process"},"background":{"type":"boolean","description":"Set to true for long-running daemons, continuous services, or GUI apps that should run detached in the background","default":false},"log_file":{"type":"string","description":"Optional custom path for output log file when running in background"}},"required":["command"]}`,
		PromptUsageTip:     "Use sys_exec for terminal commands, compiling, and running scripts. For continuous services, long-running daemons, or GUI applications (e.g. steam, games, browsers), set background: true (or append '&') so they run isolated in the background without blocking.",
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

	trimmedCmd := strings.TrimSpace(args.Command)
	if trimmedCmd == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "command cannot be empty",
		}, nil
	}

	shell := "/bin/bash"
	if _, err := exec.LookPath(shell); err != nil {
		shell = "/bin/sh"
	}

	logsDir := filepath.Join("workspace", "logs")
	_ = os.MkdirAll(logsDir, 0755)

	// Check if background execution was requested explicitly or via trailing '&'
	isBackground := args.Background || strings.HasSuffix(trimmedCmd, "&")
	if isBackground {
		return t.executeBackground(trimmedCmd, args, shell, logsDir)
	}

	return t.executeForeground(ctx, trimmedCmd, args, shell, logsDir)
}

func (t *SysExecTool) executeBackground(rawCmd string, args SysExecArgs, shell, logsDir string) (*tools.ToolResult, error) {
	cleanCmd := strings.TrimSpace(strings.TrimSuffix(rawCmd, "&"))

	logPath := args.LogFile
	if logPath == "" {
		sanitized := sanitizeForFilename(cleanCmd)
		logPath = filepath.Join(logsDir, fmt.Sprintf("exec_bg_%s_%d.log", sanitized, time.Now().Unix()))
	} else {
		_ = os.MkdirAll(filepath.Dir(logPath), 0755)
	}

	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to open background log file %s: %v", logPath, err),
		}, nil
	}

	startTime := time.Now().UTC()
	startBanner := fmt.Sprintf("=== [%s] Process started: %s (cwd: %s) ===\n", startTime.Format(time.RFC3339), cleanCmd, args.Cwd)
	_, _ = logFile.WriteString(startBanner)

	cmd := exec.Command(shell, "-c", cleanCmd)
	if args.Cwd != "" {
		cmd.Dir = args.Cwd
	}

	// Detach process group so child lives independently of Go process lifecycle
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid: true,
	}

	// Detach stdin from terminal
	devNull, devErr := os.Open(os.DevNull)
	if devErr == nil {
		cmd.Stdin = devNull
		defer devNull.Close()
	}
	cmd.Stdout = logFile
	cmd.Stderr = logFile

	if err := cmd.Start(); err != nil {
		_ = logFile.Close()
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to start background process: %v", err),
		}, nil
	}

	pid := cmd.Process.Pid
	t.appendAuditLog(logsDir, fmt.Sprintf("[%s] [BACKGROUND_START] pid=%d log=%s cmd=%s\n", startTime.Format(time.RFC3339), pid, logPath, cleanCmd))

	// Asynchronously wait for exit to reap zombies and close the log file
	go func(p *os.Process, f *os.File) {
		state, _ := p.Wait()
		exitCode := 0
		if state != nil {
			exitCode = state.ExitCode()
		}
		endBanner := fmt.Sprintf("\n=== [%s] Process %d exited with code %d ===\n", time.Now().UTC().Format(time.RFC3339), pid, exitCode)
		_, _ = f.WriteString(endBanner)
		_ = f.Close()
		t.appendAuditLog(logsDir, fmt.Sprintf("[%s] [BACKGROUND_EXIT] pid=%d exit=%d cmd=%s\n", time.Now().UTC().Format(time.RFC3339), pid, exitCode, cleanCmd))
	}(cmd.Process, logFile)

	return &tools.ToolResult{
		Stdout:   fmt.Sprintf("Process spawned in background successfully.\nPID: %d\nLog file: %s", pid, logPath),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func (t *SysExecTool) executeForeground(ctx context.Context, cmdStr string, args SysExecArgs, shell, logsDir string) (*tools.ToolResult, error) {
	timeoutSec := args.TimeoutSeconds
	if timeoutSec <= 0 {
		timeoutSec = 30
	} else if timeoutSec > 300 {
		timeoutSec = 300
	}

	execCtx, cancel := context.WithTimeout(ctx, time.Duration(timeoutSec)*time.Second)
	defer cancel()

	cmd := exec.CommandContext(execCtx, shell, "-c", cmdStr)
	if args.Cwd != "" {
		cmd.Dir = args.Cwd
	}

	// Set process group and cancel function to ensure process tree cleanup
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid: true,
	}
	cmd.WaitDelay = 2 * time.Second
	cmd.Cancel = func() error {
		if cmd.Process != nil {
			return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		}
		return nil
	}

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	start := time.Now()
	err := cmd.Run()
	duration := time.Since(start)

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

	t.appendAuditLog(logsDir, fmt.Sprintf("[%s] [FOREGROUND] exit=%d duration=%dms cmd=%s\n", time.Now().UTC().Format(time.RFC3339), exitCode, duration.Milliseconds(), cmdStr))

	return &tools.ToolResult{
		Stdout:   stdoutBuf.String(),
		Stderr:   stderrBuf.String(),
		ExitCode: exitCode,
		IsError:  isError,
	}, nil
}

func (t *SysExecTool) appendAuditLog(logsDir, entry string) {
	auditPath := filepath.Join(logsDir, "commands.log")
	f, err := os.OpenFile(auditPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err == nil {
		_, _ = f.WriteString(entry)
		_ = f.Close()
	}
}

func sanitizeForFilename(s string) string {
	parts := strings.Fields(s)
	if len(parts) == 0 {
		return "cmd"
	}
	base := filepath.Base(parts[0])
	base = strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' || r == '-' {
			return r
		}
		return '_'
	}, base)
	if len(base) > 20 {
		base = base[:20]
	}
	return base
}

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

// SysExecArgs defines the parameters accepted by sys_exec.
type SysExecArgs struct {
	Command        string `json:"command"`
	TimeoutSeconds int    `json:"timeout_seconds,omitempty"`
	Cwd            string `json:"cwd,omitempty"`
	Background     bool   `json:"background,omitempty"`
	Detach         bool   `json:"detach,omitempty"`
	LogFile        string `json:"log_file,omitempty"`
	ConfirmationID string `json:"confirmation_id,omitempty"`
}

// SysExecTool provides bash command execution with safety tiers and process detachment.
type SysExecTool struct {
	registry *ProcessRegistry
}

// NewSysExecTool constructs a SysExecTool.
func NewSysExecTool() *SysExecTool {
	return &SysExecTool{registry: GlobalProcessRegistry}
}

// Metadata returns the tool specification.
func (t *SysExecTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "sys_exec",
		Category:    "system",
		Description: "Executes a Linux bash command synchronously with timeout and safety checks, or spawns detached background/GUI processes.",
		ParameterSchema: `{"type":"object","properties":{"command":{"type":"string","description":"Bash or shell command to execute"},"timeout_seconds":{"type":"integer","description":"Command timeout deadline in seconds (default: 60)","default":60},"cwd":{"type":"string","description":"Working directory for the process"},"detach":{"type":"boolean","description":"Set to true for GUI apps or background services to run detached without waiting","default":false},"confirmation_id":{"type":"string","description":"Confirmation token returned when a destructive command was challenged"},"log_file":{"type":"string","description":"Optional custom path for output log file when running detached"}},"required":["command"]}`,
		PromptUsageTip:     "Use sys_exec for shell commands, builds, and tools. Set detach: true for GUI apps or servers. Destructive commands (rm -rf, git reset --hard) will return a confirmation_id requiring user approval.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "sys:exec",
	}
}

// Execute parses arguments, validates safety, and executes the shell command.
func (t *SysExecTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysExecArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return failResult(fmt.Sprintf("invalid arguments for sys_exec: %v", err)), nil
	}

	trimmedCmd := strings.TrimSpace(args.Command)
	if trimmedCmd == "" {
		return failResult("command cannot be empty"), nil
	}

	// Verify command safety tier
	safety := EvaluateCommandSafety(trimmedCmd)
	if safety.IsDestructive && !ValidateConfirmation(args.ConfirmationID) {
		challenge := map[string]interface{}{
			"status":          "confirmation_required",
			"tier":            safety.Tier,
			"reason":          safety.Reason,
			"command":         trimmedCmd,
			"confirmation_id": safety.ConfirmationID,
			"message":         "This command is potentially destructive and requires user confirmation.",
		}
		challengeJSON, _ := json.MarshalIndent(challenge, "", "  ")
		return &tools.ToolResult{
			Stdout:   string(challengeJSON),
			ExitCode: 0,
			IsError:  false,
		}, nil
	}

	shell := resolveShell()
	logsDir := ensureLogsDirectory(args.Cwd)

	isDetached := args.Detach || args.Background || strings.HasSuffix(trimmedCmd, "&")
	if isDetached {
		return t.executeDetached(trimmedCmd, args, shell, logsDir)
	}

	return t.executeSynchronous(ctx, trimmedCmd, args, shell, logsDir)
}

func (t *SysExecTool) executeDetached(rawCmd string, args SysExecArgs, shell, logsDir string) (*tools.ToolResult, error) {
	cleanCmd := strings.TrimSpace(strings.TrimSuffix(rawCmd, "&"))
	logPath := t.determineLogPath(args.LogFile, cleanCmd, logsDir)

	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return failResult(fmt.Sprintf("failed to open background log file %s: %v", logPath, err)), nil
	}

	cmd := exec.Command(shell, "-c", cleanCmd)
	if args.Cwd != "" {
		cmd.Dir = args.Cwd
	}

	// Detach into independent session
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}

	devNull, devErr := os.Open(os.DevNull)
	if devErr == nil {
		cmd.Stdin = devNull
		defer devNull.Close()
	}
	cmd.Stdout = logFile
	cmd.Stderr = logFile

	if err := cmd.Start(); err != nil {
		_ = logFile.Close()
		return failResult(fmt.Sprintf("failed to spawn detached process: %v", err)), nil
	}

	pid := cmd.Process.Pid
	t.registry.Register(pid, cleanCmd, logPath)
	t.appendAuditLog(logsDir, fmt.Sprintf("[DETACHED_START] pid=%d log=%s cmd=%s", pid, logPath, cleanCmd))

	// Asynchronously monitor exit to update registry and flush log
	go func(p *os.Process, f *os.File, processPID int) {
		state, _ := p.Wait()
		exitCode := 0
		if state != nil {
			exitCode = state.ExitCode()
		}
		t.registry.MarkExited(processPID, exitCode)
		_ = f.Close()
		t.appendAuditLog(logsDir, fmt.Sprintf("[DETACHED_EXIT] pid=%d exit=%d cmd=%s", processPID, exitCode, cleanCmd))
	}(cmd.Process, logFile, pid)

	result := map[string]interface{}{
		"status":   "detached",
		"pid":      pid,
		"log_file": logPath,
		"message":  "Process spawned in background successfully.",
	}
	data, _ := json.MarshalIndent(result, "", "  ")

	return &tools.ToolResult{
		Stdout:   string(data),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func (t *SysExecTool) executeSynchronous(ctx context.Context, cmdStr string, args SysExecArgs, shell, logsDir string) (*tools.ToolResult, error) {
	timeoutSec := sanitizeTimeout(args.TimeoutSeconds)
	execCtx, cancel := context.WithTimeout(ctx, time.Duration(timeoutSec)*time.Second)
	defer cancel()

	cmd := exec.CommandContext(execCtx, shell, "-c", cmdStr)
	if args.Cwd != "" {
		cmd.Dir = args.Cwd
	}

	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.WaitDelay = 2 * time.Second
	cmd.Cancel = func() error {
		if cmd.Process != nil {
			return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		}
		return nil
	}

	// Environment non-interactive guards
	cmd.Env = append(os.Environ(), "DEBIAN_FRONTEND=noninteractive", "PAGER=cat")

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

	t.appendAuditLog(logsDir, fmt.Sprintf("[SYNC] exit=%d duration=%dms cmd=%s", exitCode, duration.Milliseconds(), cmdStr))

	return &tools.ToolResult{
		Stdout:   stdoutBuf.String(),
		Stderr:   stderrBuf.String(),
		ExitCode: exitCode,
		IsError:  isError,
	}, nil
}

func (t *SysExecTool) determineLogPath(customPath, cmdStr, logsDir string) string {
	if customPath != "" {
		_ = os.MkdirAll(filepath.Dir(customPath), 0755)
		return customPath
	}
	cleanName := sanitizeFilename(cmdStr)
	return filepath.Join(logsDir, fmt.Sprintf("proc_%s_%d.log", cleanName, time.Now().Unix()))
}

func (t *SysExecTool) appendAuditLog(logsDir, entry string) {
	auditPath := filepath.Join(logsDir, "terminal_audit.log")
	f, err := os.OpenFile(auditPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err == nil {
		line := fmt.Sprintf("[%s] %s\n", time.Now().UTC().Format(time.RFC3339), entry)
		_, _ = f.WriteString(line)
		_ = f.Close()
	}
}

func resolveShell() string {
	if _, err := exec.LookPath("/bin/bash"); err == nil {
		return "/bin/bash"
	}
	return "/bin/sh"
}

func ensureLogsDirectory(cwd string) string {
	logsDir := filepath.Join("workspace", "logs")
	if cwd != "" {
		logsDir = filepath.Join(cwd, "logs")
	}
	_ = os.MkdirAll(logsDir, 0755)
	return logsDir
}

func sanitizeTimeout(seconds int) int {
	if seconds <= 0 {
		return 60
	}
	if seconds > 300 {
		return 300
	}
	return seconds
}

func sanitizeFilename(s string) string {
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

func failResult(msg string) *tools.ToolResult {
	return &tools.ToolResult{
		Stderr:   msg,
		ExitCode: 1,
		IsError:  true,
	}
}

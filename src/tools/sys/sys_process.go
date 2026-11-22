package sys

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"syscall"

	"assistant/src/tools"
)

// SysProcessArgs represents arguments passed to sys_process.
type SysProcessArgs struct {
	Action string `json:"action"` // "list", "kill", "logs"
	PID    int    `json:"pid,omitempty"`
	Signal string `json:"signal,omitempty"` // "SIGTERM", "SIGKILL"
	Lines  int    `json:"lines,omitempty"`  // Number of log lines to read
}

// SysProcessTool allows managing and inspecting tracked background processes.
type SysProcessTool struct {
	registry *ProcessRegistry
}

// NewSysProcessTool constructs a SysProcessTool backed by the global registry.
func NewSysProcessTool() *SysProcessTool {
	return &SysProcessTool{registry: GlobalProcessRegistry}
}

// Metadata returns the tool specification.
func (t *SysProcessTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "sys_process",
		Category:    "system",
		Description: "Manages tracked background processes: list active jobs, inspect their output logs, or terminate them cleanly.",
		ParameterSchema: `{"type":"object","properties":{"action":{"type":"string","enum":["list","kill","logs"],"description":"Action to perform"},"pid":{"type":"integer","description":"Target process ID (required for kill and logs)"},"signal":{"type":"string","enum":["SIGTERM","SIGKILL"],"description":"Signal to send when terminating (default: SIGTERM)","default":"SIGTERM"},"lines":{"type":"integer","description":"Number of trailing log lines to retrieve (default: 50)","default":50}},"required":["action"]}`,
		PromptUsageTip:     "Use sys_process to monitor background servers and GUI apps started by sys_exec, check their live logs, or terminate them.",
		Risk:               tools.RiskLow,
		RequiredCapability: "sys:exec",
	}
}

// Execute performs the requested process action.
func (t *SysProcessTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysProcessArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return errorResult(fmt.Sprintf("invalid arguments for sys_process: %v", err)), nil
	}

	switch args.Action {
	case "list":
		return t.handleList()
	case "kill":
		return t.handleKill(args.PID, args.Signal)
	case "logs":
		return t.handleLogs(args.PID, args.Lines)
	default:
		return errorResult(fmt.Sprintf("unknown action: %q (supported: list, kill, logs)", args.Action)), nil
	}
}

func (t *SysProcessTool) handleList() (*tools.ToolResult, error) {
	procs := t.registry.List()
	data, err := json.MarshalIndent(procs, "", "  ")
	if err != nil {
		return errorResult(fmt.Sprintf("failed to serialize process list: %v", err)), nil
	}
	return &tools.ToolResult{
		Stdout:   string(data),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func (t *SysProcessTool) handleKill(pid int, sigStr string) (*tools.ToolResult, error) {
	if pid <= 0 {
		return errorResult("pid must be a positive integer"), nil
	}

	sig := syscall.SIGTERM
	if sigStr == "SIGKILL" {
		sig = syscall.SIGKILL
	}

	// Negative PID signals the entire process group
	if err := syscall.Kill(-pid, sig); err != nil {
		if err == syscall.ESRCH {
			_ = syscall.Kill(pid, sig)
		} else {
			return errorResult(fmt.Sprintf("failed to signal process %d: %v", pid, err)), nil
		}
	}

	t.registry.MarkExited(pid, -1)
	return &tools.ToolResult{
		Stdout:   fmt.Sprintf("Signal %s sent to process %d.", sigStr, pid),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func (t *SysProcessTool) handleLogs(pid int, lineCount int) (*tools.ToolResult, error) {
	if pid <= 0 {
		return errorResult("pid must be a positive integer"), nil
	}
	if lineCount <= 0 {
		lineCount = 50
	}

	logPath := ""
	if proc, found := t.registry.Get(pid); found && proc.LogPath != "" {
		logPath = proc.LogPath
	} else {
		logPath = filepath.Join("workspace", "logs", fmt.Sprintf("proc_%d.log", pid))
	}

	lines, err := readLastLines(logPath, lineCount)
	if err != nil {
		return errorResult(fmt.Sprintf("unable to read logs for PID %d (%s): %v", pid, logPath, err)), nil
	}

	return &tools.ToolResult{
		Stdout:   lines,
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func readLastLines(filePath string, count int) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	var ring []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		ring = append(ring, scanner.Text())
		if len(ring) > count {
			ring = ring[1:]
		}
	}

	if err := scanner.Err(); err != nil {
		return "", err
	}

	result := ""
	for _, l := range ring {
		result += l + "\n"
	}
	return result, nil
}

func errorResult(msg string) *tools.ToolResult {
	return &tools.ToolResult{
		Stderr:   msg,
		ExitCode: 1,
		IsError:  true,
	}
}

package sys

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"

	"assistant/src/tools"
)

type SysPsArgs struct {
	Filter string `json:"filter,omitempty"`
	Limit  int    `json:"limit,omitempty"`
}

type SysPsTool struct{}

func NewSysPsTool() *SysPsTool {
	return &SysPsTool{}
}

func (t *SysPsTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_ps",
		Category:           "system",
		Description:        "Lists active operating system processes, memory usage, CPU, and PIDs.",
		ParameterSchema:    `{"type":"object","properties":{"filter":{"type":"string","description":"Optional process name or command filter"},"limit":{"type":"integer","description":"Maximum number of processes to return (default: 50)","default":50}}}`,
		PromptUsageTip:     "Use sys_ps to inspect background jobs, resource utilization, or find PIDs for sys_kill.",
		Risk:               tools.RiskLow,
		RequiredCapability: "sys:read",
	}
}

func (t *SysPsTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysPsArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	limit := args.Limit
	if limit <= 0 {
		limit = 50
	} else if limit > 200 {
		limit = 200
	}

	cmd := exec.CommandContext(ctx, "ps", "-eo", "pid,ppid,user,%cpu,%mem,stat,time,command", "--sort=-%cpu")
	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	if err := cmd.Run(); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to run ps: %v: %s", err, stderrBuf.String()),
		}, nil
	}

	filteredOutput := filterProcessOutput(stdoutBuf.String(), args.Filter, limit)

	return &tools.ToolResult{
		Stdout:   filteredOutput,
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func filterProcessOutput(rawOutput string, filter string, limit int) string {
	lines := strings.Split(strings.TrimSpace(rawOutput), "\n")
	if len(lines) == 0 {
		return ""
	}

	header := lines[0]
	dataLines := lines[1:]

	filterLower := strings.ToLower(filter)
	var matchedLines []string

	for _, line := range dataLines {
		if filterLower == "" || strings.Contains(strings.ToLower(line), filterLower) {
			matchedLines = append(matchedLines, line)
			if len(matchedLines) >= limit {
				break
			}
		}
	}

	result := make([]string, 0, len(matchedLines)+1)
	result = append(result, header)
	result = append(result, matchedLines...)
	return strings.Join(result, "\n")
}

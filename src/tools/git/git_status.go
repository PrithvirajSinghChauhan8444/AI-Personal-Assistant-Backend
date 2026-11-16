package git

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"

	"assistant/src/tools"
)

type GitStatusArgs struct {
	RepoPath string `json:"repo_path,omitempty"`
}

type GitStatusTool struct{}

func NewGitStatusTool() *GitStatusTool {
	return &GitStatusTool{}
}

func (t *GitStatusTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "git_status",
		Category:           "git",
		Description:        "Returns current Git branch, tracking status, staged, and unstaged modifications.",
		ParameterSchema:    `{"type":"object","properties":{"repo_path":{"type":"string","description":"Target git repository directory (default: .)"}}}`,
		PromptUsageTip:     "Use git_status before committing or reviewing pending repository changes.",
		Risk:               tools.RiskLow,
		RequiredCapability: "git:read",
	}
}

func (t *GitStatusTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GitStatusArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	repoDir := args.RepoPath
	if repoDir == "" {
		repoDir = "."
	}

	cmd := exec.CommandContext(ctx, "git", "status", "--porcelain=v1", "-b")
	cmd.Dir = repoDir

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("git status failed: %v: %s", err, stderrBuf.String()),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   stdoutBuf.String(),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

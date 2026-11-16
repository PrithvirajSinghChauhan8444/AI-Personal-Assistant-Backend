package git

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"

	"assistant/src/tools"
)

type GitCommitArgs struct {
	RepoPath string   `json:"repo_path,omitempty"`
	Message  string   `json:"message"`
	Files    []string `json:"files,omitempty"`
}

type GitCommitTool struct{}

func NewGitCommitTool() *GitCommitTool {
	return &GitCommitTool{}
}

func (t *GitCommitTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "git_commit",
		Category:           "git",
		Description:        "Stages files and creates a Git commit with a structured commit message.",
		ParameterSchema:    `{"type":"object","properties":{"repo_path":{"type":"string","description":"Target git repository directory (default: .)"},"message":{"type":"string","description":"Git commit message"},"files":{"type":"array","items":{"type":"string"},"description":"List of file paths to stage (if empty, stages all changes)"}},"required":["message"]}`,
		PromptUsageTip:     "Use git_commit with descriptive commit messages following conventional commit guidelines.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "git:write",
	}
}

func (t *GitCommitTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GitCommitArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for git_commit: %v", err),
		}, nil
	}

	if strings.TrimSpace(args.Message) == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "commit message cannot be empty",
		}, nil
	}

	repoDir := args.RepoPath
	if repoDir == "" {
		repoDir = "."
	}

	if err := stageFiles(ctx, repoDir, args.Files); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to stage files: %v", err),
		}, nil
	}

	cmd := exec.CommandContext(ctx, "git", "commit", "-m", args.Message)
	cmd.Dir = repoDir

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("git commit failed: %v: %s", err, stderrBuf.String()),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   stdoutBuf.String(),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func stageFiles(ctx context.Context, repoDir string, files []string) error {
	var cmd *exec.Cmd
	if len(files) == 0 {
		cmd = exec.CommandContext(ctx, "git", "add", "-A")
	} else {
		args := append([]string{"add", "--"}, files...)
		cmd = exec.CommandContext(ctx, "git", args...)
	}
	cmd.Dir = repoDir

	var stderrBuf bytes.Buffer
	cmd.Stderr = &stderrBuf

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("%w: %s", err, stderrBuf.String())
	}
	return nil
}

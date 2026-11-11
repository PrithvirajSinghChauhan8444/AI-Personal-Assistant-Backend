package git

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"

	"assistant/src/tools"
)

type GitDiffArgs struct {
	RepoPath string `json:"repo_path,omitempty"`
	Target   string `json:"target,omitempty"`
	Staged   bool   `json:"staged,omitempty"`
}

type GitDiffTool struct{}

func NewGitDiffTool() *GitDiffTool {
	return &GitDiffTool{}
}

func (t *GitDiffTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "git_diff",
		Category:           "git",
		Description:        "Returns unified diff against working directory, staged changes, or a target branch/commit.",
		ParameterSchema:    `{"type":"object","properties":{"repo_path":{"type":"string","description":"Target git repository directory (default: .)"},"target":{"type":"string","description":"Commit, branch, or ref to diff against (e.g. HEAD, origin/main)"},"staged":{"type":"boolean","description":"Set true to diff staged changes"}}}`,
		PromptUsageTip:     "Use git_diff to review modifications before creating commits or pull requests.",
		Risk:               tools.RiskLow,
		RequiredCapability: "git:read",
	}
}

func (t *GitDiffTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GitDiffArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	repoDir := args.RepoPath
	if repoDir == "" {
		repoDir = "."
	}

	cmdArgs := []string{"diff"}
	if args.Staged {
		cmdArgs = append(cmdArgs, "--staged")
	} else if args.Target != "" {
		cmdArgs = append(cmdArgs, args.Target)
	}

	cmd := exec.CommandContext(ctx, "git", cmdArgs...)
	cmd.Dir = repoDir

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("git diff failed: %v: %s", err, stderrBuf.String()),
		}, nil
	}

	output := stdoutBuf.String()
	if output == "" {
		output = "(no changes)"
	}

	return &tools.ToolResult{
		Stdout:   output,
		ExitCode: 0,
		IsError:  false,
	}, nil
}

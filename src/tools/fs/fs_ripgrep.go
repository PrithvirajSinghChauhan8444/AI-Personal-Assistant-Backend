package fs

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"

	"assistant/src/tools"
)

type FsRipgrepArgs struct {
	Query         string `json:"query"`
	Path          string `json:"path,omitempty"`
	FilePattern   string `json:"file_pattern,omitempty"`
	CaseSensitive bool   `json:"case_sensitive,omitempty"`
	MaxMatches    int    `json:"max_matches,omitempty"`
}

type FsRipgrepTool struct{}

func NewFsRipgrepTool() *FsRipgrepTool {
	return &FsRipgrepTool{}
}

func (t *FsRipgrepTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "fs_ripgrep",
		Category:           "filesystem",
		Description:        "High-speed regex and text search across files and directories.",
		ParameterSchema:    `{"type":"object","properties":{"query":{"type":"string","description":"Regex or text string to search for"},"path":{"type":"string","description":"Directory or file to search within (default: .)"},"file_pattern":{"type":"string","description":"Glob pattern filtering file names (e.g. *.go)"},"case_sensitive":{"type":"boolean","description":"Whether the search is case-sensitive"},"max_matches":{"type":"integer","description":"Maximum matching lines to return (default: 100)"}},"required":["query"]}`,
		PromptUsageTip:     "Use fs_ripgrep to locate functions, variables, errors, or keywords across the codebase.",
		Risk:               tools.RiskLow,
		RequiredCapability: "fs:read",
	}
}

func (t *FsRipgrepTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args FsRipgrepArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for fs_ripgrep: %v", err),
		}, nil
	}

	if args.Query == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "query cannot be empty",
		}, nil
	}

	searchPath := args.Path
	if searchPath == "" {
		searchPath = "."
	}

	maxMatches := args.MaxMatches
	if maxMatches <= 0 {
		maxMatches = 100
	}

	if rgPath, err := exec.LookPath("rg"); err == nil {
		return executeRipgrepBinary(ctx, rgPath, searchPath, args, maxMatches)
	}

	return executeFallbackRegexSearch(searchPath, args, maxMatches)
}

func executeRipgrepBinary(ctx context.Context, rgPath, searchPath string, args FsRipgrepArgs, maxMatches int) (*tools.ToolResult, error) {
	cmdArgs := []string{"-n", "--no-heading", "--color=never", fmt.Sprintf("--max-count=%d", maxMatches)}

	if !args.CaseSensitive {
		cmdArgs = append(cmdArgs, "-i")
	}

	if args.FilePattern != "" {
		cmdArgs = append(cmdArgs, "-g", args.FilePattern)
	}

	cmdArgs = append(cmdArgs, args.Query, searchPath)

	cmd := exec.CommandContext(ctx, rgPath, cmdArgs...)
	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok && exitErr.ExitCode() == 1 {
			return &tools.ToolResult{
				Stdout:   "(no matches found)",
				ExitCode: 0,
				IsError:  false,
			}, nil
		}
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("ripgrep error: %v: %s", err, stderrBuf.String()),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   stdoutBuf.String(),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func executeFallbackRegexSearch(root string, args FsRipgrepArgs, maxMatches int) (*tools.ToolResult, error) {
	flags := ""
	if !args.CaseSensitive {
		flags = "(?i)"
	}

	pattern, err := regexp.Compile(flags + args.Query)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid regex pattern: %v", err),
		}, nil
	}

	var matches []string

	_ = filepath.WalkDir(root, func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil || d.IsDir() {
			return nil
		}

		if args.FilePattern != "" {
			matched, _ := filepath.Match(args.FilePattern, d.Name())
			if !matched {
				return nil
			}
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return nil
		}

		lines := strings.Split(string(content), "\n")
		for i, line := range lines {
			if pattern.MatchString(line) {
				matches = append(matches, fmt.Sprintf("%s:%d:%s", path, i+1, strings.TrimSpace(line)))
				if len(matches) >= maxMatches {
					return fs.SkipAll
				}
			}
		}
		return nil
	})

	if len(matches) == 0 {
		return &tools.ToolResult{
			Stdout:   "(no matches found)",
			ExitCode: 0,
			IsError:  false,
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   strings.Join(matches, "\n"),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

package fs

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"assistant/src/tools"
)

type FsWriteArgs struct {
	Path    string `json:"path"`
	Content string `json:"content"`
	Append  bool   `json:"append,omitempty"`
}

type FsWriteTool struct{}

func NewFsWriteTool() *FsWriteTool {
	return &FsWriteTool{}
}

func (t *FsWriteTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "fs_write",
		Category:           "filesystem",
		Description:        "Writes or overwrites a file atomically via tempfile replacement, or appends to an existing file.",
		ParameterSchema:    `{"type":"object","properties":{"path":{"type":"string","description":"Absolute or relative target file path"},"content":{"type":"string","description":"Text content to write"},"append":{"type":"boolean","description":"Whether to append rather than overwrite"}},"required":["path","content"]}`,
		PromptUsageTip:     "Use fs_write to create or modify source code and artifacts. Missing parent directories are created automatically.",
		Risk:               tools.RiskMedium,
		RequiredCapability: "fs:write",
	}
}

func (t *FsWriteTool) Execute(_ context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args FsWriteArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for fs_write: %v", err),
		}, nil
	}

	if args.Path == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "path cannot be empty",
		}, nil
	}

	dir := filepath.Dir(args.Path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to create directory tree for %q: %v", args.Path, err),
		}, nil
	}

	var writeErr error
	if args.Append {
		writeErr = appendToFile(args.Path, args.Content)
	} else {
		writeErr = atomicWriteFile(args.Path, args.Content)
	}

	if writeErr != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to write file %q: %v", args.Path, writeErr),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   fmt.Sprintf("successfully wrote %d bytes to %s", len(args.Content), args.Path),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func atomicWriteFile(targetPath, content string) error {
	dir := filepath.Dir(targetPath)
	tempFile, err := os.CreateTemp(dir, ".tmp_fswrite_*")
	if err != nil {
		return err
	}
	tempName := tempFile.Name()

	defer func() {
		_ = os.Remove(tempName)
	}()

	if _, err := tempFile.WriteString(content); err != nil {
		_ = tempFile.Close()
		return err
	}

	if err := tempFile.Close(); err != nil {
		return err
	}

	return os.Rename(tempName, targetPath)
}

func appendToFile(targetPath, content string) error {
	file, err := os.OpenFile(targetPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer file.Close()

	_, err = file.WriteString(content)
	return err
}

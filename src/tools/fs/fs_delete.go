package fs

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"assistant/src/tools"
)

type FsDeleteArgs struct {
	Path      string `json:"path"`
	Recursive bool   `json:"recursive,omitempty"`
}

type FsDeleteTool struct{}

func NewFsDeleteTool() *FsDeleteTool {
	return &FsDeleteTool{}
}

func (t *FsDeleteTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "fs_delete",
		Category:           "filesystem",
		Description:        "Deletes a file or directory on disk (high risk operation requiring HITL clearance).",
		ParameterSchema:    `{"type":"object","properties":{"path":{"type":"string","description":"Absolute or relative path to delete"},"recursive":{"type":"boolean","description":"Set true to recursively remove directories"}},"required":["path"]}`,
		PromptUsageTip:     "Use fs_delete with extreme caution. Deletions trigger human authorization prompts.",
		Risk:               tools.RiskHigh,
		RequiredCapability: "fs:delete",
	}
}

func (t *FsDeleteTool) Execute(_ context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args FsDeleteArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for fs_delete: %v", err),
		}, nil
	}

	cleanPath := filepath.Clean(strings.TrimSpace(args.Path))
	if cleanPath == "" || cleanPath == "." || cleanPath == "/" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("refusing to delete unsafe target %q", args.Path),
		}, nil
	}

	info, err := os.Stat(cleanPath)
	if err != nil {
		if os.IsNotExist(err) {
			return &tools.ToolResult{
				Stdout:   fmt.Sprintf("target %q already does not exist", cleanPath),
				ExitCode: 0,
				IsError:  false,
			}, nil
		}
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to stat target %q: %v", cleanPath, err),
		}, nil
	}

	if info.IsDir() && !args.Recursive {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("target %q is a directory; set recursive=true to delete", cleanPath),
		}, nil
	}

	if args.Recursive {
		err = os.RemoveAll(cleanPath)
	} else {
		err = os.Remove(cleanPath)
	}

	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to remove %q: %v", cleanPath, err),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   fmt.Sprintf("successfully deleted %s", cleanPath),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

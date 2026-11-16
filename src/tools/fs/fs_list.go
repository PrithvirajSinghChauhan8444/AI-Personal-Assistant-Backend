package fs

import (
	"context"
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"

	"assistant/src/tools"
)

type FsListArgs struct {
	Path      string `json:"path,omitempty"`
	Recursive bool   `json:"recursive,omitempty"`
	MaxDepth  int    `json:"max_depth,omitempty"`
}

type FileEntry struct {
	Path     string    `json:"path"`
	IsDir    bool      `json:"is_dir"`
	Size     int64     `json:"size"`
	Modified time.Time `json:"modified"`
}

type FsListTool struct{}

func NewFsListTool() *FsListTool {
	return &FsListTool{}
}

func (t *FsListTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "fs_list",
		Category:           "filesystem",
		Description:        "Lists files and directories with sizes, timestamps, and tree traversal options.",
		ParameterSchema:    `{"type":"object","properties":{"path":{"type":"string","description":"Directory path to list (default: .)"},"recursive":{"type":"boolean","description":"Recursively traverse subdirectories"},"max_depth":{"type":"integer","description":"Maximum recursion depth (default: 2)"}}}`,
		PromptUsageTip:     "Use fs_list to discover files, check project layouts, and verify folder structures.",
		Risk:               tools.RiskLow,
		RequiredCapability: "fs:read",
	}
}

func (t *FsListTool) Execute(_ context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args FsListArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	targetPath := args.Path
	if targetPath == "" {
		targetPath = "."
	}

	info, err := os.Stat(targetPath)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("cannot access path %q: %v", targetPath, err),
		}, nil
	}

	if !info.IsDir() {
		return &tools.ToolResult{
			Stdout:   formatSingleEntry(targetPath, info),
			ExitCode: 0,
			IsError:  false,
		}, nil
	}

	maxDepth := args.MaxDepth
	if maxDepth <= 0 {
		maxDepth = 2
	}

	entries, err := collectEntries(targetPath, args.Recursive, maxDepth)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to list directory %q: %v", targetPath, err),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   formatEntriesTable(entries),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func collectEntries(root string, recursive bool, maxDepth int) ([]FileEntry, error) {
	var entries []FileEntry
	cleanRoot := filepath.Clean(root)

	err := filepath.WalkDir(cleanRoot, func(currentPath string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return nil
		}

		if currentPath == cleanRoot {
			return nil
		}

		relPath, _ := filepath.Rel(cleanRoot, currentPath)
		depth := strings.Count(relPath, string(filepath.Separator)) + 1

		if depth > maxDepth {
			if d.IsDir() {
				return fs.SkipDir
			}
			return nil
		}

		if !recursive && depth > 1 {
			if d.IsDir() {
				return fs.SkipDir
			}
			return nil
		}

		info, err := d.Info()
		if err != nil {
			return nil
		}

		entries = append(entries, FileEntry{
			Path:     relPath,
			IsDir:    d.IsDir(),
			Size:     info.Size(),
			Modified: info.ModTime(),
		})

		return nil
	})

	return entries, err
}

func formatSingleEntry(path string, info os.FileInfo) string {
	return fmt.Sprintf("FILE\t%8d\t%s\t%s", info.Size(), info.ModTime().Format("2006-01-02 15:04"), path)
}

func formatEntriesTable(entries []FileEntry) string {
	if len(entries) == 0 {
		return "(empty directory)"
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("%-5s\t%-10s\t%-16s\t%s\n", "TYPE", "SIZE", "MODIFIED", "PATH"))
	sb.WriteString(strings.Repeat("-", 60) + "\n")

	for _, e := range entries {
		typeStr := "FILE"
		if e.IsDir {
			typeStr = "DIR"
		}
		modStr := e.Modified.Format("2006-01-02 15:04")
		sb.WriteString(fmt.Sprintf("%-5s\t%10d\t%s\t%s\n", typeStr, e.Size, modStr, e.Path))
	}

	return sb.String()
}

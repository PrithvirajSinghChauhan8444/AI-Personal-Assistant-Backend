package fs

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"assistant/src/tools"
)

type FsReadArgs struct {
	Path        string `json:"path"`
	StartLine   int    `json:"start_line,omitempty"`
	EndLine     int    `json:"end_line,omitempty"`
	ByteOffset  int64  `json:"byte_offset,omitempty"`
	LengthBytes int64  `json:"length_bytes,omitempty"`
}

type FsReadTool struct{}

func NewFsReadTool() *FsReadTool {
	return &FsReadTool{}
}

func (t *FsReadTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "fs_read",
		Category:           "filesystem",
		Description:        "Reads UTF-8 text from disk with line and byte slicing options.",
		ParameterSchema:    `{"type":"object","properties":{"path":{"type":"string","description":"Absolute or relative file path to read"},"start_line":{"type":"integer","description":"1-based starting line number (inclusive)"},"end_line":{"type":"integer","description":"1-based ending line number (inclusive)"},"byte_offset":{"type":"integer","description":"Byte offset into the file"},"length_bytes":{"type":"integer","description":"Maximum number of bytes to read"}},"required":["path"]}`,
		PromptUsageTip:     "Use fs_read to view configuration, code, and documents. Use start_line/end_line for targeted inspection of large files.",
		Risk:               tools.RiskLow,
		RequiredCapability: "fs:read",
	}
}

func (t *FsReadTool) Execute(_ context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args FsReadArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for fs_read: %v", err),
		}, nil
	}

	if args.Path == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "path cannot be empty",
		}, nil
	}

	info, err := os.Stat(args.Path)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("cannot access path %q: %v", args.Path, err),
		}, nil
	}

	if info.IsDir() {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("path %q is a directory, use fs_list instead", args.Path),
		}, nil
	}

	content, err := os.ReadFile(args.Path)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to read file %q: %v", args.Path, err),
		}, nil
	}

	output := processReadSlicing(content, args)

	return &tools.ToolResult{
		Stdout:   output,
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func processReadSlicing(data []byte, args FsReadArgs) string {
	if args.ByteOffset > 0 || args.LengthBytes > 0 {
		return sliceBytes(data, args.ByteOffset, args.LengthBytes)
	}

	if args.StartLine > 0 || args.EndLine > 0 {
		return sliceLines(string(data), args.StartLine, args.EndLine)
	}

	return string(data)
}

func sliceBytes(data []byte, offset, length int64) string {
	totalLen := int64(len(data))
	if offset >= totalLen {
		return ""
	}

	end := totalLen
	if length > 0 && offset+length < totalLen {
		end = offset + length
	}

	return string(data[offset:end])
}

func sliceLines(content string, startLine, endLine int) string {
	lines := strings.Split(content, "\n")
	totalLines := len(lines)

	start := 1
	if startLine > 1 {
		start = startLine
	}
	if start > totalLines {
		return ""
	}

	end := totalLines
	if endLine > 0 && endLine < totalLines {
		end = endLine
	}
	if end < start {
		return ""
	}

	return strings.Join(lines[start-1:end], "\n")
}

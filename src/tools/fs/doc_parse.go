package fs

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"assistant/src/tools"
)

type DocParseArgs struct {
	Path     string `json:"path"`
	MaxPages int    `json:"max_pages,omitempty"`
}

type DocParseTool struct {
	pythonBin string
	repoRoot  string
}

func NewDocParseTool() *DocParseTool {
	bin, root := resolvePythonBinary()
	return &DocParseTool{
		pythonBin: bin,
		repoRoot:  root,
	}
}

func (t *DocParseTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "doc_parse",
		Category:           "filesystem",
		Description:        "Parses binary documents (PDF, Word DOCX, Excel XLSX, PPTX, CSV, Image metadata) into structured Markdown.",
		ParameterSchema:    `{"type":"object","properties":{"path":{"type":"string","description":"Absolute or relative path to document file"},"max_pages":{"type":"integer","description":"Maximum number of pages or sheets to extract (default: 50)"}},"required":["path"]}`,
		PromptUsageTip:     "Use doc_parse whenever the user asks to read, analyze, or summarize a PDF, DOCX, spreadsheet, or presentation.",
		Risk:               tools.RiskLow,
		RequiredCapability: "fs:read",
	}
}

func (t *DocParseTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args DocParseArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for doc_parse: %v", err),
		}, nil
	}

	cleanPath := strings.TrimSpace(args.Path)
	if cleanPath == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "path cannot be empty",
		}, nil
	}

	absPath, err := filepath.Abs(cleanPath)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("cannot resolve absolute path: %v", err),
		}, nil
	}

	if _, err := os.Stat(absPath); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("file not found: %s", absPath),
		}, nil
	}

	maxPages := args.MaxPages
	if maxPages <= 0 {
		maxPages = 50
	}

	cmdCtx, cancel := context.WithTimeout(ctx, 45*time.Second)
	defer cancel()

	cmd := exec.CommandContext(cmdCtx, t.pythonBin, "-m", "src.tools.media.parser", absPath, "--max-pages", fmt.Sprintf("%d", maxPages))
	cmd.Dir = t.repoRoot
	cmd.Env = append(os.Environ(), fmt.Sprintf("PYTHONPATH=%s", t.repoRoot))

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	if err := cmd.Run(); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stdout:   stdoutBuf.String(),
			Stderr:   fmt.Sprintf("doc_parse failed: %v: %s", err, stderrBuf.String()),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   strings.TrimSpace(stdoutBuf.String()),
		Stderr:   stderrBuf.String(),
		ExitCode: 0,
	}, nil
}

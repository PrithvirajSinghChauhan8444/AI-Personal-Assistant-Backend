package sys

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"assistant/src/tools"
)

// SysClipboardCopyArgs defines arguments for clipboard copy.
type SysClipboardCopyArgs struct {
	Text string `json:"text"`
}

// SysClipboardCopyTool copies text to the operating system clipboard.
type SysClipboardCopyTool struct{}

func NewSysClipboardCopyTool() *SysClipboardCopyTool {
	return &SysClipboardCopyTool{}
}

func (t *SysClipboardCopyTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "sys_clipboard_copy",
		Category:    "system",
		Description: "Copies text to the system clipboard using Wayland (wl-copy) or X11 (xclip/xsel).",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"text": {"type": "string", "description": "Text to place into system clipboard"}
			},
			"required": ["text"]
		}`,
		PromptUsageTip:     "Use sys_clipboard_copy when asked to copy text, links, or code for the user.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysClipboardCopyTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args SysClipboardCopyArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	execCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	// Try wl-copy (Wayland)
	if _, err := exec.LookPath("wl-copy"); err == nil && (os.Getenv("WAYLAND_DISPLAY") != "" || isBinaryAvailable("wl-copy")) {
		cmd := exec.CommandContext(execCtx, "wl-copy")
		cmd.Stdin = strings.NewReader(args.Text)
		if err := cmd.Run(); err == nil {
			return &tools.ToolResult{Stdout: fmt.Sprintf("Successfully copied %d characters to clipboard via wl-copy.", len(args.Text))}, nil
		}
	}

	// Try xclip (X11)
	if _, err := exec.LookPath("xclip"); err == nil {
		cmd := exec.CommandContext(execCtx, "xclip", "-selection", "clipboard")
		cmd.Stdin = strings.NewReader(args.Text)
		if err := cmd.Run(); err == nil {
			return &tools.ToolResult{Stdout: fmt.Sprintf("Successfully copied %d characters to clipboard via xclip.", len(args.Text))}, nil
		}
	}

	// Try xsel (X11 fallback)
	if _, err := exec.LookPath("xsel"); err == nil {
		cmd := exec.CommandContext(execCtx, "xsel", "--clipboard", "--input")
		cmd.Stdin = strings.NewReader(args.Text)
		if err := cmd.Run(); err == nil {
			return &tools.ToolResult{Stdout: fmt.Sprintf("Successfully copied %d characters to clipboard via xsel.", len(args.Text))}, nil
		}
	}

	return &tools.ToolResult{
		IsError:  true,
		ExitCode: 1,
		Stderr:   "clipboard copy failed: neither wl-copy, xclip, nor xsel is available or working",
	}, nil
}

// SysClipboardPasteTool pastes text from the system clipboard.
type SysClipboardPasteTool struct{}

func NewSysClipboardPasteTool() *SysClipboardPasteTool {
	return &SysClipboardPasteTool{}
}

func (t *SysClipboardPasteTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "sys_clipboard_paste",
		Category:           "system",
		Description:        "Retrieves and returns text content from the system clipboard.",
		ParameterSchema:    `{"type":"object","properties":{}}`,
		PromptUsageTip:     "Use sys_clipboard_paste to read what the user currently has copied.",
		Risk:               tools.RiskLow,
		RequiredCapability: "system:hardware",
	}
}

func (t *SysClipboardPasteTool) Execute(ctx context.Context, _ string) (*tools.ToolResult, error) {
	execCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	// Try wl-paste
	if _, err := exec.LookPath("wl-paste"); err == nil && (os.Getenv("WAYLAND_DISPLAY") != "" || isBinaryAvailable("wl-paste")) {
		cmd := exec.CommandContext(execCtx, "wl-paste", "--no-newline")
		var out bytes.Buffer
		cmd.Stdout = &out
		if err := cmd.Run(); err == nil {
			return &tools.ToolResult{Stdout: out.String()}, nil
		}
	}

	// Try xclip
	if _, err := exec.LookPath("xclip"); err == nil {
		cmd := exec.CommandContext(execCtx, "xclip", "-selection", "clipboard", "-o")
		var out bytes.Buffer
		cmd.Stdout = &out
		if err := cmd.Run(); err == nil {
			return &tools.ToolResult{Stdout: out.String()}, nil
		}
	}

	// Try xsel
	if _, err := exec.LookPath("xsel"); err == nil {
		cmd := exec.CommandContext(execCtx, "xsel", "--clipboard", "--output")
		var out bytes.Buffer
		cmd.Stdout = &out
		if err := cmd.Run(); err == nil {
			return &tools.ToolResult{Stdout: out.String()}, nil
		}
	}

	return &tools.ToolResult{
		IsError:  true,
		ExitCode: 1,
		Stderr:   "clipboard paste failed: neither wl-paste, xclip, nor xsel is available",
	}, nil
}

func isBinaryAvailable(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

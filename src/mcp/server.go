package mcp

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"assistant/src/tools"
)

const maxScanBufferSize = 10 * 1024 * 1024 // 10MB max line buffer for large tool outputs

// Server abstracts an MCP server instance for testing and lifecycle control.
type Server interface {
	Name() string
	Start(ctx context.Context) error
	Close() error
	ListTools(ctx context.Context) ([]ToolInfo, error)
	CallTool(ctx context.Context, toolName string, args map[string]any) (*tools.ToolResult, error)
}

// StdioServer runs an MCP server as a sub-process over standard I/O pipes.
type StdioServer struct {
	name       string
	cfg        ServerConfig
	mu         sync.Mutex
	cmd        *exec.Cmd
	stdin      io.WriteCloser
	scanner    *bufio.Scanner
	reqCounter uint64
	started    bool
}

// NewStdioServer creates a new StdioServer instance for the given server name and config.
func NewStdioServer(name string, cfg ServerConfig) *StdioServer {
	return &StdioServer{
		name: name,
		cfg:  cfg,
	}
}

// Name returns the identifier of this server.
func (s *StdioServer) Name() string {
	return s.name
}

// Start launches the process and completes the MCP initialization handshake.
func (s *StdioServer) Start(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.started {
		return nil
	}

	resolvedCmd := resolvePath(s.cfg.Command)
	resolvedArgs := make([]string, len(s.cfg.Args))
	for i, arg := range s.cfg.Args {
		resolvedArgs[i] = resolvePath(arg)
	}

	cmd := exec.CommandContext(ctx, resolvedCmd, resolvedArgs...)
	cmd.Env = s.buildEnvironment()

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdin pipe: %w", err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		_ = stdin.Close()
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		_ = stdin.Close()
		return fmt.Errorf("failed to start process: %w", err)
	}

	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 64*1024), maxScanBufferSize)

	s.cmd = cmd
	s.stdin = stdin
	s.scanner = scanner
	s.started = true

	if err := s.performHandshakeLocked(ctx); err != nil {
		s.stopLocked()
		return fmt.Errorf("handshake failed: %w", err)
	}

	return nil
}

// ListTools queries the server for its available tools via tools/list.
func (s *StdioServer) ListTools(ctx context.Context) ([]ToolInfo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.started {
		return nil, fmt.Errorf("server %q is not running", s.name)
	}

	resp, err := s.sendRequestLocked(ctx, "tools/list", map[string]any{})
	if err != nil {
		return nil, err
	}

	if resp.Error != nil {
		return nil, fmt.Errorf("tools/list error (%d): %s", resp.Error.Code, resp.Error.Message)
	}

	var result ListToolsResult
	if err := json.Unmarshal(resp.Result, &result); err != nil {
		return nil, fmt.Errorf("failed to parse tools/list result: %w", err)
	}

	return result.Tools, nil
}

// CallTool invokes a tool on this server and returns a normalized ToolResult.
func (s *StdioServer) CallTool(ctx context.Context, toolName string, args map[string]any) (*tools.ToolResult, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	startTime := time.Now()

	if !s.started {
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("server %q is not running", s.name),
			DurationMs: 0,
		}, nil
	}

	params := CallToolParams{
		Name:      toolName,
		Arguments: args,
	}

	resp, err := s.sendRequestLocked(ctx, "tools/call", params)
	durationMs := time.Since(startTime).Milliseconds()

	if err != nil {
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("call to %s failed: %v", toolName, err),
			DurationMs: durationMs,
		}, nil
	}

	if resp.Error != nil {
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("tool error (%d): %s", resp.Error.Code, resp.Error.Message),
			DurationMs: durationMs,
		}, nil
	}

	var callResult CallToolResult
	if err := json.Unmarshal(resp.Result, &callResult); err != nil {
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("failed to parse tool output: %v", err),
			DurationMs: durationMs,
		}, nil
	}

	var outputBuilder strings.Builder
	for _, item := range callResult.Content {
		if item.Text != "" {
			outputBuilder.WriteString(item.Text)
		}
	}

	return &tools.ToolResult{
		Stdout:     outputBuilder.String(),
		IsError:    callResult.IsError,
		ExitCode:   btoi(callResult.IsError),
		DurationMs: durationMs,
	}, nil
}

// Close gracefully terminates the server process.
func (s *StdioServer) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.stopLocked()
	return nil
}

func (s *StdioServer) performHandshakeLocked(ctx context.Context) error {
	params := InitializeParams{
		ProtocolVersion: DefaultProtocolVersion,
		Capabilities:    ClientCapabilities{},
		ClientInfo: ImplementationInfo{
			Name:    ClientName,
			Version: ClientVersion,
		},
	}

	resp, err := s.sendRequestLocked(ctx, "initialize", params)
	if err != nil {
		return err
	}
	if resp.Error != nil {
		return fmt.Errorf("initialize rejected: %s", resp.Error.Message)
	}

	// Send initialized notification (no id needed for notification in JSON-RPC)
	notif := map[string]any{
		"jsonrpc": "2.0",
		"method":  "notifications/initialized",
	}
	notifBytes, _ := json.Marshal(notif)
	_, _ = s.stdin.Write(append(notifBytes, '\n'))

	return nil
}

func (s *StdioServer) sendRequestLocked(ctx context.Context, method string, params any) (*JSONRPCResponse, error) {
	reqID := atomic.AddUint64(&s.reqCounter, 1)
	req := JSONRPCRequest{
		JSONRPC: "2.0",
		ID:      reqID,
		Method:  method,
		Params:  params,
	}

	reqBytes, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request error: %w", err)
	}

	if _, err := s.stdin.Write(append(reqBytes, '\n')); err != nil {
		return nil, fmt.Errorf("write error: %w", err)
	}

	for s.scanner.Scan() {
		line := strings.TrimSpace(s.scanner.Text())
		if line == "" {
			continue
		}

		var resp JSONRPCResponse
		if err := json.Unmarshal([]byte(line), &resp); err != nil {
			// Ignore non-JSON output (like server banner / stdout logs)
			continue
		}

		if resp.ID == reqID {
			return &resp, nil
		}
	}

	if err := s.scanner.Err(); err != nil {
		return nil, fmt.Errorf("scanner error: %w", err)
	}

	return nil, io.ErrUnexpectedEOF
}

func (s *StdioServer) stopLocked() {
	if s.stdin != nil {
		_ = s.stdin.Close()
		s.stdin = nil
	}
	if s.cmd != nil && s.cmd.Process != nil {
		_ = s.cmd.Process.Kill()
		_ = s.cmd.Wait()
		s.cmd = nil
	}
	s.started = false
	s.scanner = nil
}

func (s *StdioServer) buildEnvironment() []string {
	env := os.Environ()
	for k, v := range s.cfg.Env {
		val := v
		if k == "PYTHONPATH" {
			val = resolvePath(v)
		}
		env = append(env, fmt.Sprintf("%s=%s", k, val))
	}
	return env
}

func resolvePath(path string) string {
	if filepath.IsAbs(path) || strings.HasPrefix(path, "-") {
		return path
	}
	if _, err := os.Stat(path); err == nil {
		return path
	}
	candidates := []string{
		filepath.Join("..", path),
		filepath.Join("..", "..", path),
		filepath.Join("..", "..", "..", path),
	}
	for _, cand := range candidates {
		if _, err := os.Stat(cand); err == nil {
			return cand
		}
	}
	return path
}

func btoi(b bool) int {
	if b {
		return 1
	}
	return 0
}

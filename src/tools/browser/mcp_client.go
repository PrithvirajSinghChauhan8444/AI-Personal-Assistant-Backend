package browser

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"assistant/src/tools"
)

// PlaywrightMCPClient manages a long-lived Playwright MCP process over stdio JSON-RPC.
type PlaywrightMCPClient struct {
	mu         sync.Mutex
	cmd        *exec.Cmd
	stdin      io.WriteCloser
	scanner    *bufio.Scanner
	reqCounter uint64
	started    bool

	browserType    string
	profileName    string
	executablePath string
	userDataDir    string
	attachCDP      bool
	cdpURL         string
	viewportSize   string
	headless       bool
}

var (
	defaultClient     *PlaywrightMCPClient
	defaultClientOnce sync.Once
)

// tryLoadDotEnv attempts to parse key-value pairs from .env files if not already exported.
func tryLoadDotEnv() {
	paths := []string{".env", "config/.env", "../config/.env", "../../config/.env"}
	for _, p := range paths {
		if data, err := os.ReadFile(p); err == nil {
			lines := strings.Split(string(data), "\n")
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if line == "" || strings.HasPrefix(line, "#") {
					continue
				}
				parts := strings.SplitN(line, "=", 2)
				if len(parts) == 2 {
					key := strings.TrimSpace(parts[0])
					val := strings.TrimSpace(parts[1])
					val = strings.Trim(val, `"'`)
					if os.Getenv(key) == "" {
						_ = os.Setenv(key, val)
					}
				}
			}
			return
		}
	}
}

// resolveBrowser detects and validates executable paths for brave, chrome, or chromium.
func resolveBrowser(browserType string) (resolvedType string, executablePath string) {
	bType := strings.ToLower(strings.TrimSpace(browserType))
	if bType == "" {
		bType = "auto"
	}

	searchCandidates := map[string][]string{
		"brave": {
			"brave",
			"brave-browser",
			"/usr/bin/brave",
			"/usr/bin/brave-browser",
			"/opt/brave.com/brave/brave-browser",
			"/snap/bin/brave",
		},
		"chrome": {
			"google-chrome-stable",
			"google-chrome",
			"chrome",
			"/usr/bin/google-chrome-stable",
			"/usr/bin/google-chrome",
			"/opt/google/chrome/google-chrome",
		},
		"chromium": {
			"chromium",
			"chromium-browser",
			"/usr/bin/chromium",
			"/usr/lib/chromium/chromium",
			"/usr/bin/chromium-browser",
			"/snap/bin/chromium",
		},
	}

	findExe := func(candidates []string) string {
		for _, cand := range candidates {
			if strings.Contains(cand, "/") {
				if info, err := os.Stat(cand); err == nil && !info.IsDir() {
					return cand
				}
			} else {
				if p, err := exec.LookPath(cand); err == nil {
					return p
				}
			}
		}
		return ""
	}

	switch bType {
	case "brave":
		exe := findExe(searchCandidates["brave"])
		if exe != "" {
			return "brave", exe
		}
		return "brave", "/usr/bin/brave"
	case "chrome", "google-chrome":
		exe := findExe(searchCandidates["chrome"])
		if exe != "" {
			return "chrome", exe
		}
		return "chrome", "/usr/bin/google-chrome"
	case "chromium":
		exe := findExe(searchCandidates["chromium"])
		if exe != "" {
			return "chromium", exe
		}
		return "chromium", "/usr/bin/chromium"
	case "auto":
		fallthrough
	default:
		// Check in priority order: brave -> chrome -> chromium
		for _, typ := range []string{"brave", "chrome", "chromium"} {
			if exe := findExe(searchCandidates[typ]); exe != "" {
				return typ, exe
			}
		}
		// Fallback default
		return "chromium", "/usr/bin/chromium"
	}
}

// resolveUserDataDir computes the persistent profile directory path for the assistant.
func resolveUserDataDir(browserType, profileName, explicitDir string) string {
	if explicitDir != "" {
		return expandHome(explicitDir)
	}

	pName := strings.TrimSpace(profileName)
	if pName == "" {
		pName = "assistant-profile"
	}

	home, err := os.UserHomeDir()
	if err != nil {
		home = "."
	}

	// Produces e.g. ~/.config/brave-assistant-profile or ~/.config/chrome-assistant-profile
	folderName := fmt.Sprintf("%s-%s", browserType, pName)
	return filepath.Join(home, ".config", folderName)
}

// GetDefaultClient returns the singleton Playwright MCP client initialized from environment settings.
func GetDefaultClient() *PlaywrightMCPClient {
	defaultClientOnce.Do(func() {
		tryLoadDotEnv()

		browserType := os.Getenv("BROWSER_TYPE")
		resolvedType, autoExecPath := resolveBrowser(browserType)

		execPath := os.Getenv("BROWSER_EXECUTABLE_PATH")
		if execPath == "" {
			execPath = autoExecPath
		}

		profileName := os.Getenv("BROWSER_PROFILE_NAME")
		if profileName == "" {
			profileName = "assistant-profile"
		}

		userDir := resolveUserDataDir(resolvedType, profileName, os.Getenv("BROWSER_USER_DATA_DIR"))

		attachCDP := strings.ToLower(os.Getenv("BROWSER_ATTACH_CDP")) == "true"
		cdpURL := os.Getenv("BROWSER_CDP_URL")
		if cdpURL == "" {
			cdpURL = "http://localhost:9222"
		}

		viewport := os.Getenv("BROWSER_VIEWPORT")
		if viewport == "" {
			viewport = "1280x720"
		}

		headless := strings.ToLower(os.Getenv("BROWSER_HEADLESS")) == "true"

		// Fallback to browser_config.json if present
		if cfgData, err := os.ReadFile("src/agents/browser/browser_config.json"); err == nil {
			var bCfg struct {
				Headless *bool  `json:"headless"`
				CDPURL   string `json:"cdp_url"`
			}
			if err := json.Unmarshal(cfgData, &bCfg); err == nil {
				if bCfg.Headless != nil && os.Getenv("BROWSER_HEADLESS") == "" {
					headless = *bCfg.Headless
				}
				if bCfg.CDPURL != "" && os.Getenv("BROWSER_CDP_URL") == "" {
					cdpURL = bCfg.CDPURL
				}
			}
		}

		defaultClient = &PlaywrightMCPClient{
			browserType:    resolvedType,
			profileName:    profileName,
			executablePath: expandHome(execPath),
			userDataDir:    expandHome(userDir),
			attachCDP:      attachCDP,
			cdpURL:         cdpURL,
			viewportSize:   viewport,
			headless:       headless,
		}
	})
	return defaultClient
}

func expandHome(path string) string {
	if strings.HasPrefix(path, "~/") {
		home, err := os.UserHomeDir()
		if err == nil {
			return strings.Replace(path, "~", home, 1)
		}
	}
	return path
}

func isCDPOpen(url string) bool {
	host := "127.0.0.1:9222"
	if strings.Contains(url, "://") {
		parts := strings.Split(url, "://")
		if len(parts) > 1 {
			host = strings.Trim(parts[1], "/")
		}
	}
	conn, err := net.DialTimeout("tcp", host, 500*time.Millisecond)
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
}

func (c *PlaywrightMCPClient) ensureStartedLocked() error {
	if c.started && c.cmd != nil && c.cmd.Process != nil {
		return nil
	}

	args := []string{"-y", "@playwright/mcp@latest"}

	// Attach via CDP only if explicitly enabled by user and port is open
	if c.attachCDP && c.cdpURL != "" && isCDPOpen(c.cdpURL) {
		args = append(args, fmt.Sprintf("--cdp-endpoint=%s", c.cdpURL))
	} else {
		// Launch dedicated browser instance with persistent user profile directory
		if c.executablePath != "" {
			if _, err := os.Stat(c.executablePath); err == nil {
				args = append(args, fmt.Sprintf("--executable-path=%s", c.executablePath))
			}
		}
		if c.userDataDir != "" {
			_ = os.MkdirAll(c.userDataDir, 0755)
			args = append(args, fmt.Sprintf("--user-data-dir=%s", c.userDataDir))
		}
		if c.viewportSize != "" {
			args = append(args, fmt.Sprintf("--viewport-size=%s", c.viewportSize))
		}
		if c.headless {
			args = append(args, "--headless")
		}
	}

	cmd := exec.Command("npx", args...)
	cmd.Stderr = os.Stderr

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("failed to open mcp stdin pipe: %w", err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		_ = stdin.Close()
		return fmt.Errorf("failed to open mcp stdout pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		_ = stdin.Close()
		_ = stdout.Close()
		return fmt.Errorf("failed to start playwright mcp process: %w", err)
	}

	c.cmd = cmd
	c.stdin = stdin
	c.scanner = bufio.NewScanner(stdout)
	// Buffer up to 10MB for snapshots and full DOM responses
	buf := make([]byte, 1024*1024)
	c.scanner.Buffer(buf, 10*1024*1024)
	c.started = true

	// Step 1: Initialize handshake
	initReq := map[string]any{
		"jsonrpc": "2.0",
		"id":      atomic.AddUint64(&c.reqCounter, 1),
		"method":  "initialize",
		"params": map[string]any{
			"protocolVersion": "2024-11-05",
			"capabilities":    map[string]any{},
			"clientInfo": map[string]any{
				"name":    "hermes-go-bridge",
				"version": "1.0.0",
			},
		},
	}

	initBytes, _ := json.Marshal(initReq)
	if _, err := c.stdin.Write(append(initBytes, '\n')); err != nil {
		c.stopLocked()
		return fmt.Errorf("failed to send initialize frame: %w", err)
	}

	if !c.scanner.Scan() {
		c.stopLocked()
		return fmt.Errorf("playwright mcp terminated during initialization")
	}

	// Step 2: notifications/initialized
	notif := map[string]any{
		"jsonrpc": "2.0",
		"method":  "notifications/initialized",
		"params":  map[string]any{},
	}
	notifBytes, _ := json.Marshal(notif)
	_, _ = c.stdin.Write(append(notifBytes, '\n'))

	return nil
}

func (c *PlaywrightMCPClient) stopLocked() {
	if c.stdin != nil {
		_ = c.stdin.Close()
		c.stdin = nil
	}
	if c.cmd != nil && c.cmd.Process != nil {
		_ = c.cmd.Process.Kill()
		_ = c.cmd.Wait()
		c.cmd = nil
	}
	c.started = false
	c.scanner = nil
}

// Close gracefully terminates the underlying Playwright MCP child process.
func (c *PlaywrightMCPClient) Close() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.stopLocked()
}

// CallTool invokes a tool on Playwright MCP and returns the standardized ToolResult.
func (c *PlaywrightMCPClient) CallTool(ctx context.Context, toolName string, arguments map[string]any) (*tools.ToolResult, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	startTime := time.Now()

	if err := c.ensureStartedLocked(); err != nil {
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("playwright mcp unavailable: %v", err),
			DurationMs: time.Since(startTime).Milliseconds(),
		}, nil
	}

	reqID := atomic.AddUint64(&c.reqCounter, 1)
	req := map[string]any{
		"jsonrpc": "2.0",
		"id":      reqID,
		"method":  "tools/call",
		"params": map[string]any{
			"name":      toolName,
			"arguments": arguments,
		},
	}

	reqBytes, err := json.Marshal(req)
	if err != nil {
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("failed to marshal tool request: %v", err),
			DurationMs: time.Since(startTime).Milliseconds(),
		}, nil
	}

	if _, err := c.stdin.Write(append(reqBytes, '\n')); err != nil {
		c.stopLocked()
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("failed to write to playwright mcp: %v", err),
			DurationMs: time.Since(startTime).Milliseconds(),
		}, nil
	}

	type rpcResponse struct {
		JSONRPC string `json:"jsonrpc"`
		ID      uint64 `json:"id"`
		Result  struct {
			IsError bool `json:"isError"`
			Content []struct {
				Type string `json:"type"`
				Text string `json:"text"`
			} `json:"content"`
		} `json:"result"`
		Error *struct {
			Code    int    `json:"code"`
			Message string `json:"message"`
		} `json:"error"`
	}

	if !c.scanner.Scan() {
		c.stopLocked()
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     "playwright mcp closed connection prematurely",
			DurationMs: time.Since(startTime).Milliseconds(),
		}, nil
	}

	line := c.scanner.Bytes()
	var resp rpcResponse
	if err := json.Unmarshal(line, &resp); err != nil {
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("failed to decode playwright mcp response: %v", err),
			DurationMs: time.Since(startTime).Milliseconds(),
		}, nil
	}

	duration := time.Since(startTime).Milliseconds()

	if resp.Error != nil {
		return &tools.ToolResult{
			IsError:    true,
			ExitCode:   1,
			Stderr:     fmt.Sprintf("playwright mcp error (%d): %s", resp.Error.Code, resp.Error.Message),
			DurationMs: duration,
		}, nil
	}

	var sb strings.Builder
	for _, item := range resp.Result.Content {
		if item.Text != "" {
			if sb.Len() > 0 {
				sb.WriteString("\n")
			}
			sb.WriteString(item.Text)
		}
	}

	stdout := sb.String()
	if stdout == "" && !resp.Result.IsError {
		stdout = fmt.Sprintf("Tool %s completed successfully.", toolName)
	}

	return &tools.ToolResult{
		Stdout:     stdout,
		Stderr:     "",
		ExitCode:   0,
		IsError:    resp.Result.IsError,
		DurationMs: duration,
	}, nil
}

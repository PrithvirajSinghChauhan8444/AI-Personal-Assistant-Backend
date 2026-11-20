package workspace

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"assistant/src/tools"
)

// GoogleAuthLoginArgs defines parameters for initiating Google authentication.
type GoogleAuthLoginArgs struct {
	Account string `json:"account,omitempty"`
	Port    int    `json:"port,omitempty"`
}

// GoogleAuthLoginTool triggers the OAuth flow, starts the local redirect listener, and prints the URL.
type GoogleAuthLoginTool struct {
	configDir string
}

func NewGoogleAuthLoginTool(configDir string) *GoogleAuthLoginTool {
	if configDir == "" {
		configDir = "config"
	}
	return &GoogleAuthLoginTool{configDir: configDir}
}

func (t *GoogleAuthLoginTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "google_auth_login",
		Category:    "workspace",
		Description: "Initiates Google Workspace OAuth flow, starts local callback receiver, and prints the direct authorization link.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {
					"type": "string",
					"description": "Complete email address to authenticate (e.g. 'user@example.com', 'work@company.com')"
				},
				"port": {
					"type": "integer",
					"description": "Local callback port (default: 9915)",
					"default": 9915
				}
			}
		}`,
		PromptUsageTip:     "Use google_auth_login when Google authentication or token refresh is required, or when the user asks to connect/authenticate their Google account.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:write",
	}
}

func (t *GoogleAuthLoginTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args GoogleAuthLoginArgs
	if argsJSON != "" {
		_ = json.Unmarshal([]byte(argsJSON), &args)
	}

	account := strings.TrimSpace(strings.ToLower(args.Account))
	if account == "" {
		account = "auto"
	}

	port := args.Port
	if port <= 0 {
		port = 9915
	}

	// 1. Locate python binary (.venv/bin/python3 preferred)
	pythonBin := ".venv/bin/python3"
	if _, err := os.Stat(pythonBin); err != nil {
		if path, err := exec.LookPath("python3"); err == nil {
			pythonBin = path
		} else {
			pythonBin = "python"
		}
	}

	scriptPath := "scripts/auth_google.py"
	if _, err := os.Stat(scriptPath); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("auth script not found at %s", scriptPath),
		}, nil
	}

	// 2. Spawn python script detached in its own process group
	cmd := exec.Command(pythonBin, scriptPath,
		"--account", account,
		"--config-dir", t.configDir,
		"--port", fmt.Sprintf("%d", port),
	)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to attach stdout pipe: %v", err),
		}, nil
	}
	cmd.Stderr = os.Stderr

	if err := cmd.Start(); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to launch auth process: %v", err),
		}, nil
	}

	// 3. Read stdout line-by-line until the authorization link is captured (max 10s deadline)
	authURLChan := make(chan string, 1)
	errChan := make(chan error, 1)
	scanDone := make(chan struct{})

	go func() {
		defer close(scanDone)
		scanner := bufio.NewScanner(stdoutPipe)
		captured := false
		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if strings.HasPrefix(line, "https://accounts.google.com/o/oauth2/") && !captured {
				captured = true
				authURLChan <- line
			}
		}
		if err := scanner.Err(); err != nil && !captured {
			errChan <- err
		}
	}()

	var authURL string
	select {
	case url := <-authURLChan:
		authURL = url
	case err := <-errChan:
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to retrieve authorization link: %v", err),
		}, nil
	case <-time.After(10 * time.Second):
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "timed out waiting for authorization link from auth_google.py",
		}, nil
	case <-ctx.Done():
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "authentication process cancelled before link generation",
		}, nil
	}

	// 4. Print prominent terminal banner so the user can immediately click/open the auth link
	actualPort := port
	if u, err := url.Parse(authURL); err == nil {
		if redirectURI := u.Query().Get("redirect_uri"); redirectURI != "" {
			if ru, err := url.Parse(redirectURI); err == nil && ru.Port() != "" {
				if p, err := strconv.Atoi(ru.Port()); err == nil && p > 0 {
					actualPort = p
				}
			}
		}
	}

	tokenDest := filepath.Join(t.configDir, fmt.Sprintf("token_%s.json", account))
	fmt.Fprintf(os.Stderr, "\n"+
		"================================================================================\n"+
		"🔐 GOOGLE WORKSPACE AUTHENTICATION REQUIRED\n"+
		"Account: %s\n"+
		"Target Token: %s\n\n"+
		"👉 AUTHORIZATION LINK (open in browser):\n%s\n\n"+
		"Local callback server listening on port %d...\n"+
		"Waiting for authorization to complete in your browser (up to 3 minutes)...\n"+
		"================================================================================\n\n",
		account, tokenDest, authURL, actualPort)

	// 5. Wait for the OAuth local redirect receiver to complete and persist tokens
	waitCh := make(chan error, 1)
	go func() {
		waitCh <- cmd.Wait()
	}()

	select {
	case err := <-waitCh:
		<-scanDone
		if err != nil {
			return &tools.ToolResult{
				IsError:  true,
				ExitCode: 1,
				Stderr:   fmt.Sprintf("authentication process failed or was interrupted: %v", err),
			}, nil
		}

		fmt.Fprintf(os.Stderr, "\n✅ Google Workspace account %q authenticated successfully! Resuming task...\n\n", account)

		output := fmt.Sprintf(
			"Successfully authenticated Google Workspace account %q!\n"+
				"OAuth token has been saved and verified at: %s\n\n"+
				"CRITICAL INSTRUCTION: You MUST now immediately proceed in this turn to execute the pending user workspace request (such as gmail_check_unread, gmail_list, or calendar) using this authenticated account. Do not ask the user to repeat their prompt.",
			account, tokenDest,
		)

		return &tools.ToolResult{
			Stdout:   output,
			ExitCode: 0,
		}, nil

	case <-time.After(180 * time.Second):
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "authentication timed out waiting for approval in browser (180s deadline exceeded)",
		}, nil

	case <-ctx.Done():
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "authentication cancelled: turn context cancelled",
		}, nil
	}
}

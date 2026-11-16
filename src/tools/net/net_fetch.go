package net

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"assistant/src/tools"
)

type NetFetchArgs struct {
	URL            string            `json:"url"`
	Method         string            `json:"method,omitempty"`
	Headers        map[string]string `json:"headers,omitempty"`
	Body           string            `json:"body,omitempty"`
	TimeoutSeconds int               `json:"timeout_seconds,omitempty"`
}

type NetFetchTool struct {
	client *http.Client
}

func NewNetFetchTool() *NetFetchTool {
	return &NetFetchTool{
		client: &http.Client{
			Timeout: 15 * time.Second,
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				if len(via) >= 10 {
					return fmt.Errorf("stopped after 10 redirects")
				}
				return nil
			},
		},
	}
}

func (t *NetFetchTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "net_fetch",
		Category:           "net",
		Description:        "Executes high-speed HTTP requests with custom headers, redirect limits, and response inspection.",
		ParameterSchema:    `{"type":"object","properties":{"url":{"type":"string","description":"Target HTTP/HTTPS URL"},"method":{"type":"string","description":"HTTP method: GET, POST, PUT, DELETE, PATCH, HEAD (default: GET)"},"headers":{"type":"object","additionalProperties":{"type":"string"},"description":"Custom HTTP headers"},"body":{"type":"string","description":"Request body string"},"timeout_seconds":{"type":"integer","description":"Request timeout in seconds (default: 15)"}},"required":["url"]}`,
		PromptUsageTip:     "Use net_fetch to call external REST APIs, download files, or check remote HTTP endpoints.",
		Risk:               tools.RiskLow,
		RequiredCapability: "net:read",
	}
}

func (t *NetFetchTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args NetFetchArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for net_fetch: %v", err),
		}, nil
	}

	if strings.TrimSpace(args.URL) == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "url cannot be empty",
		}, nil
	}

	method := strings.ToUpper(strings.TrimSpace(args.Method))
	if method == "" {
		method = http.MethodGet
	}

	timeout := 15 * time.Second
	if args.TimeoutSeconds > 0 {
		timeout = time.Duration(args.TimeoutSeconds) * time.Second
	}

	reqCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	var bodyReader io.Reader
	if args.Body != "" {
		bodyReader = strings.NewReader(args.Body)
	}

	req, err := http.NewRequestWithContext(reqCtx, method, args.URL, bodyReader)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed to construct request: %v", err),
		}, nil
	}

	req.Header.Set("User-Agent", "AI-Personal-Assistant/1.0 (Linux x86_64)")
	for k, v := range args.Headers {
		req.Header.Set(k, v)
	}

	resp, err := t.client.Do(req)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("HTTP request failed: %v", err),
		}, nil
	}
	defer resp.Body.Close()

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("failed reading response body: %v", err),
		}, nil
	}

	output := fmt.Sprintf("HTTP %d %s\nContent-Type: %s\nContent-Length: %d\n\n%s",
		resp.StatusCode,
		resp.Status,
		resp.Header.Get("Content-Type"),
		len(respBytes),
		string(respBytes),
	)

	isError := resp.StatusCode >= 400
	exitCode := 0
	if isError {
		exitCode = 1
	}

	return &tools.ToolResult{
		Stdout:   output,
		ExitCode: exitCode,
		IsError:  isError,
	}, nil
}

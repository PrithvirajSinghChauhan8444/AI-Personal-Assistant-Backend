package net

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"assistant/src/tools"
)

// NetWeatherArgs defines arguments to fetch weather.
type NetWeatherArgs struct {
	Location string `json:"location"`
	Format   string `json:"format,omitempty"` // "summary" (default) or "detailed"
}

// NetWeatherTool retrieves current weather conditions without an API key using wttr.in.
type NetWeatherTool struct {
	client *http.Client
}

func NewNetWeatherTool() *NetWeatherTool {
	return &NetWeatherTool{
		client: &http.Client{Timeout: 10 * time.Second},
	}
}

func (t *NetWeatherTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "net_weather",
		Category:    "net",
		Description: "Fetches current weather conditions and temperature for a given city or location.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"location": {"type": "string", "description": "City name or location (e.g. 'London', 'Agra', 'Tokyo')"},
				"format": {"type": "string", "enum": ["summary", "detailed"], "description": "Format: 'summary' (concise text) or 'detailed' (JSON forecasts)", "default": "summary"}
			},
			"required": ["location"]
		}`,
		PromptUsageTip:     "Use net_weather to answer questions about weather, forecasts, or temperature in any city.",
		Risk:               tools.RiskLow,
		RequiredCapability: "net:read",
	}
}

func (t *NetWeatherTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args NetWeatherArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
	}

	location := strings.TrimSpace(args.Location)
	if location == "" {
		location = "Agra"
	}

	var endpoint string
	if args.Format == "detailed" {
		endpoint = fmt.Sprintf("https://wttr.in/%s?format=j1", url.PathEscape(location))
	} else {
		endpoint = fmt.Sprintf("https://wttr.in/%s?format=%%C+%%t+(feels+like+%%f),+Humidity:+%%h,+Wind:+%%w", url.PathEscape(location))
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to construct weather request: %v", err)}, nil
	}
	req.Header.Set("User-Agent", "curl/7.68.0") // wttr.in prefers CLI user agents for plain text

	resp, err := t.client.Do(req)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("weather fetch failed: %v", err)}, nil
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to read response: %v", err)}, nil
	}

	if resp.StatusCode != http.StatusOK {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("weather service returned %d: %s", resp.StatusCode, string(bodyBytes))}, nil
	}

	resultText := strings.TrimSpace(string(bodyBytes))
	return &tools.ToolResult{Stdout: fmt.Sprintf("Weather for %s: %s", location, resultText)}, nil
}

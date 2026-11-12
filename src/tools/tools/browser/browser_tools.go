package browser

import (
	"context"
	"encoding/json"
	"fmt"

	"assistant/src/tools"
)

// BaseBrowserTool provides a shared MCP client and execution wrapper.
type BaseBrowserTool struct {
	client      *PlaywrightMCPClient
	name        string
	mcpToolName string
	description string
	schema      string
	tip         string
	risk        tools.RiskLevel
	capability  string
}

func (t *BaseBrowserTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               t.name,
		Category:           "browser",
		Description:        t.description,
		ParameterSchema:    t.schema,
		PromptUsageTip:     t.tip,
		Risk:               t.risk,
		RequiredCapability: t.capability,
	}
}

func (t *BaseBrowserTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args map[string]any
	if argsJSON != "" && argsJSON != "{}" {
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return &tools.ToolResult{
				IsError:  true,
				ExitCode: 1,
				Stderr:   fmt.Sprintf("invalid arguments for %s: %v", t.name, err),
			}, nil
		}
	} else {
		args = make(map[string]any)
	}

	// Normalize arguments between legacy/Go tools and native Playwright MCP
	mcpArgs := make(map[string]any)
	for k, v := range args {
		mcpArgs[k] = v
	}

	targetName := t.mcpToolName
	if targetName == "" {
		targetName = t.name
	}

	if t.name == "browser_click" || t.name == "browser_type" {
		if sel, ok := mcpArgs["selector"]; ok && mcpArgs["target"] == nil {
			mcpArgs["target"] = sel
		}
	}

	return t.client.CallTool(ctx, targetName, mcpArgs)
}

// NewBrowserNavigateTool registers browser_navigate.
func NewBrowserNavigateTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_navigate",
		mcpToolName: "browser_navigate",
		description: "Navigates to a target URL in the browser and waits for the page to load.",
		schema:      `{"type":"object","properties":{"url":{"type":"string","description":"Full HTTP/HTTPS URL to open"}},"required":["url"]}`,
		tip:         "Always check page content after navigation to confirm successful load.",
		risk:        tools.RiskLow,
		capability:  "browser:read",
	}
}

// NewBrowserSnapshotTool registers browser_snapshot.
func NewBrowserSnapshotTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_snapshot",
		mcpToolName: "browser_snapshot",
		description: "Captures accessibility tree snapshot of the page with interactive element references and roles.",
		schema:      `{"type":"object","properties":{}}`,
		tip:         "Use immediately after navigation to inspect headings, buttons, links, and content.",
		risk:        tools.RiskLow,
		capability:  "browser:read",
	}
}

// NewBrowserReadContentTool registers browser_read_content (alias to browser_snapshot).
func NewBrowserReadContentTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_read_content",
		mcpToolName: "browser_snapshot",
		description: "Reads the visible text, headers, and interactive DOM layout of the current browser page.",
		schema:      `{"type":"object","properties":{"max_length":{"type":"integer","description":"Max characters"}}}`,
		tip:         "Use to inspect page text, articles, or locate buttons/links for subsequent clicks.",
		risk:        tools.RiskLow,
		capability:  "browser:read",
	}
}

// NewBrowserClickTool registers browser_click.
func NewBrowserClickTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_click",
		mcpToolName: "browser_click",
		description: "Clicks an interactive button, link, or element on the current page.",
		schema:      `{"type":"object","properties":{"selector":{"type":"string","description":"CSS selector or text"},"target":{"type":"string","description":"Target element ref from snapshot"}}}`,
		tip:         "Specify an accessible text label or target element reference from snapshot.",
		risk:        tools.RiskMedium,
		capability:  "browser:interact",
	}
}

// NewBrowserTypeTool registers browser_type.
func NewBrowserTypeTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_type",
		mcpToolName: "browser_type",
		description: "Types text into an active form input or search field.",
		schema:      `{"type":"object","properties":{"selector":{"type":"string","description":"CSS selector"},"target":{"type":"string","description":"Target element ref"},"text":{"type":"string","description":"Text string to type"}},"required":["text"]}`,
		tip:         "Use to submit queries, enter filters, or fill forms.",
		risk:        tools.RiskMedium,
		capability:  "browser:interact",
	}
}

// NewBrowserTakeScreenshotTool registers browser_take_screenshot.
func NewBrowserTakeScreenshotTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_take_screenshot",
		mcpToolName: "browser_take_screenshot",
		description: "Captures a visual screenshot of the current page viewport or element.",
		schema:      `{"type":"object","properties":{"fullPage":{"type":"boolean","description":"Capture entire scrollable page","default":false},"filename":{"type":"string","description":"Optional file path"}}}`,
		tip:         "Use to visually verify web dashboards, graphs, or UI layouts.",
		risk:        tools.RiskLow,
		capability:  "browser:read",
	}
}

// NewBrowserScreenshotTool registers browser_screenshot (alias to browser_take_screenshot).
func NewBrowserScreenshotTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_screenshot",
		mcpToolName: "browser_take_screenshot",
		description: "Captures a visual screenshot of the current page viewport or element.",
		schema:      `{"type":"object","properties":{"full_page":{"type":"boolean","description":"Capture entire scrollable page","default":false}}}`,
		tip:         "Use to visually verify web dashboards, graphs, or UI errors.",
		risk:        tools.RiskLow,
		capability:  "browser:read",
	}
}

// NewBrowserTabsTool registers browser_tabs.
func NewBrowserTabsTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_tabs",
		mcpToolName: "browser_tabs",
		description: "List, create, close, or select browser tabs.",
		schema:      `{"type":"object","properties":{"action":{"type":"string","enum":["list","new","close","select"],"description":"Operation to perform"},"index":{"type":"number"},"url":{"type":"string"}},"required":["action"]}`,
		tip:         "Use to manage multiple active tabs.",
		risk:        tools.RiskLow,
		capability:  "browser:interact",
	}
}

// NewBrowserWaitForTool registers browser_wait_for.
func NewBrowserWaitForTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_wait_for",
		mcpToolName: "browser_wait_for",
		description: "Wait for text to appear or disappear or a specified time to pass.",
		schema:      `{"type":"object","properties":{"time":{"type":"number","description":"Time to wait in seconds"},"text":{"type":"string"}}}`,
		tip:         "Use when dynamic content takes time to render.",
		risk:        tools.RiskLow,
		capability:  "browser:read",
	}
}

// NewBrowserNavigateBackTool registers browser_navigate_back.
func NewBrowserNavigateBackTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_navigate_back",
		mcpToolName: "browser_navigate_back",
		description: "Navigates back to the previous page in history.",
		schema:      `{"type":"object","properties":{}}`,
		tip:         "Use to return to previous page.",
		risk:        tools.RiskLow,
		capability:  "browser:read",
	}
}

// NewBrowserCloseTool registers browser_close.
func NewBrowserCloseTool(client *PlaywrightMCPClient) tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return &BaseBrowserTool{
		client:      client,
		name:        "browser_close",
		mcpToolName: "browser_close",
		description: "Closes the current browser tab or window.",
		schema:      `{"type":"object","properties":{}}`,
		tip:         "Use when finished with browser automation task.",
		risk:        tools.RiskMedium,
		capability:  "browser:interact",
	}
}

// GetAllBrowserTools returns all browser tools wired to the Playwright MCP client.
func GetAllBrowserTools(client *PlaywrightMCPClient) []tools.Tool {
	if client == nil {
		client = GetDefaultClient()
	}
	return []tools.Tool{
		NewBrowserNavigateTool(client),
		NewBrowserSnapshotTool(client),
		NewBrowserReadContentTool(client),
		NewBrowserClickTool(client),
		NewBrowserTypeTool(client),
		NewBrowserTakeScreenshotTool(client),
		NewBrowserScreenshotTool(client),
		NewBrowserTabsTool(client),
		NewBrowserWaitForTool(client),
		NewBrowserNavigateBackTool(client),
		NewBrowserCloseTool(client),
	}
}

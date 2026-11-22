package researchtools

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"

	"assistant/src/tools"
)

// ============================================================================
// 1. NetSearchTool
// ============================================================================

// NetSearchArgs defines arguments for web search.
type NetSearchArgs struct {
	Query string `json:"query"`
	Limit int    `json:"limit,omitempty"`
}

// SearchResultItem represents an individual web search result.
type SearchResultItem struct {
	Title   string `json:"title"`
	URL     string `json:"url"`
	Snippet string `json:"snippet"`
}

// NetSearchTool performs web searches via DuckDuckGo or SearxNG.
type NetSearchTool struct {
	client *http.Client
}

// NewNetSearchTool constructs a new NetSearchTool.
func NewNetSearchTool() *NetSearchTool {
	return &NetSearchTool{
		client: &http.Client{
			Timeout: 15 * time.Second,
		},
	}
}

func (t *NetSearchTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "net_search",
		Category:           "net",
		Description:        "Queries web search engines to retrieve relevant search snippets, titles, and URLs.",
		ParameterSchema:    `{"type":"object","properties":{"query":{"type":"string","description":"Search keywords or question"},"limit":{"type":"integer","description":"Maximum number of search results to return (default: 10)"}},"required":["query"]}`,
		PromptUsageTip:     "Use net_search to find live documentation, news, facts, and external references.",
		Risk:               tools.RiskLow,
		RequiredCapability: "net:read",
	}
}

func (t *NetSearchTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args NetSearchArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for net_search: %v", err),
		}, nil
	}

	query := strings.TrimSpace(args.Query)
	if query == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "query cannot be empty",
		}, nil
	}

	limit := args.Limit
	if limit <= 0 {
		limit = 10
	} else if limit > 25 {
		limit = 25
	}

	if searxURL := os.Getenv("SEARXNG_URL"); searxURL != "" {
		return t.searchSearx(ctx, searxURL, query, limit)
	}

	return t.searchDuckDuckGo(ctx, query, limit)
}

func (t *NetSearchTool) searchDuckDuckGo(ctx context.Context, query string, limit int) (*tools.ToolResult, error) {
	endpoint := fmt.Sprintf("https://html.duckduckgo.com/html/?q=%s", url.QueryEscape(query))

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, Stderr: err.Error()}, nil
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

	resp, err := t.client.Do(req)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("search request failed: %v", err),
		}, nil
	}
	defer resp.Body.Close()

	bodyBytes, _ := io.ReadAll(resp.Body)
	results := parseDuckDuckGoHTML(string(bodyBytes), limit)

	if len(results) == 0 {
		return &tools.ToolResult{
			Stdout:   fmt.Sprintf("No results found for query: %s", query),
			ExitCode: 0,
			IsError:  false,
		}, nil
	}

	outJSON, _ := json.MarshalIndent(results, "", "  ")
	return &tools.ToolResult{
		Stdout:   string(outJSON),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func (t *NetSearchTool) searchSearx(ctx context.Context, baseURL, query string, limit int) (*tools.ToolResult, error) {
	endpoint := fmt.Sprintf("%s/search?q=%s&format=json", strings.TrimSuffix(baseURL, "/"), url.QueryEscape(query))
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, Stderr: err.Error()}, nil
	}

	resp, err := t.client.Do(req)
	if err != nil {
		return &tools.ToolResult{IsError: true, Stderr: err.Error()}, nil
	}
	defer resp.Body.Close()

	var searxResp struct {
		Results []struct {
			Title   string `json:"title"`
			URL     string `json:"url"`
			Content string `json:"content"`
		} `json:"results"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&searxResp); err != nil {
		return &tools.ToolResult{IsError: true, Stderr: fmt.Sprintf("failed parsing searx response: %v", err)}, nil
	}

	var items []SearchResultItem
	for i, r := range searxResp.Results {
		if i >= limit {
			break
		}
		items = append(items, SearchResultItem{
			Title:   r.Title,
			URL:     r.URL,
			Snippet: r.Content,
		})
	}

	outJSON, _ := json.MarshalIndent(items, "", "  ")
	return &tools.ToolResult{
		Stdout:   string(outJSON),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

var (
	titleRegex   = regexp.MustCompile(`<a class="result__url"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>`)
	snippetRegex = regexp.MustCompile(`<a class="result__snippet"[^>]*>([\s\S]*?)</a>`)
)

func parseDuckDuckGoHTML(html string, limit int) []SearchResultItem {
	var items []SearchResultItem

	blocks := strings.Split(html, `class="result results_links results_links_deep`)
	for i := 1; i < len(blocks); i++ {
		if len(items) >= limit {
			break
		}
		block := blocks[i]

		titleMatch := titleRegex.FindStringSubmatch(block)
		var resultURL, title string
		if len(titleMatch) >= 3 {
			resultURL = cleanDuckDuckGoURL(titleMatch[1])
			title = stripHTML(titleMatch[2])
		}

		var snippet string
		snippetMatch := snippetRegex.FindStringSubmatch(block)
		if len(snippetMatch) >= 2 {
			snippet = stripHTML(snippetMatch[1])
		}

		if title != "" && resultURL != "" {
			items = append(items, SearchResultItem{
				Title:   title,
				URL:     resultURL,
				Snippet: snippet,
			})
		}
	}

	return items
}

func cleanDuckDuckGoURL(rawURL string) string {
	if strings.Contains(rawURL, "uddg=") {
		parsed, err := url.Parse(rawURL)
		if err == nil {
			if target := parsed.Query().Get("uddg"); target != "" {
				return target
			}
		}
	}
	return rawURL
}

func stripHTML(input string) string {
	re := regexp.MustCompile(`<[^>]*>`)
	cleaned := re.ReplaceAllString(input, "")
	cleaned = strings.ReplaceAll(cleaned, "&amp;", "&")
	cleaned = strings.ReplaceAll(cleaned, "&quot;", "\"")
	cleaned = strings.ReplaceAll(cleaned, "&#39;", "'")
	cleaned = strings.ReplaceAll(cleaned, "&lt;", "<")
	cleaned = strings.ReplaceAll(cleaned, "&gt;", ">")
	return strings.TrimSpace(cleaned)
}

// ============================================================================
// 2. NetFetchTool
// ============================================================================

// NetFetchArgs defines arguments for making HTTP requests.
type NetFetchArgs struct {
	URL            string            `json:"url"`
	Method         string            `json:"method,omitempty"`
	Headers        map[string]string `json:"headers,omitempty"`
	Body           string            `json:"body,omitempty"`
	TimeoutSeconds int               `json:"timeout_seconds,omitempty"`
}

// NetFetchTool executes outbound HTTP requests.
type NetFetchTool struct {
	client *http.Client
}

// NewNetFetchTool constructs a new NetFetchTool.
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

// ============================================================================
// 3. NetWeatherTool
// ============================================================================

// NetWeatherArgs defines arguments to fetch weather.
type NetWeatherArgs struct {
	Location string `json:"location"`
	Format   string `json:"format,omitempty"`
}

// NetWeatherTool retrieves current weather conditions using wttr.in.
type NetWeatherTool struct {
	client *http.Client
}

// NewNetWeatherTool constructs a new NetWeatherTool.
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
	req.Header.Set("User-Agent", "curl/7.68.0")

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

// ============================================================================
// Consolidated Tool Exporter for Research Worker
// ============================================================================

// GetAllTools returns all Go-native tools associated with the Research Agent.
func GetAllTools() []tools.Tool {
	return []tools.Tool{
		NewNetSearchTool(),
		NewNetFetchTool(),
		NewNetWeatherTool(),
	}
}

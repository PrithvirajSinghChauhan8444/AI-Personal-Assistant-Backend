package net

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

type NetSearchArgs struct {
	Query string `json:"query"`
	Limit int    `json:"limit,omitempty"`
}

type SearchResultItem struct {
	Title   string `json:"title"`
	URL     string `json:"url"`
	Snippet string `json:"snippet"`
}

type NetSearchTool struct {
	client *http.Client
}

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

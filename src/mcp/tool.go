package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"assistant/src/tools"
)

// MCPTool adapts an MCP-discovered tool into the assistant's native Tool interface.
type MCPTool struct {
	server         Server
	serverName     string
	originalName   string
	namespacedName string
	description    string
	schema         string
	risk           tools.RiskLevel
}

// NewMCPTool creates a new Tool adapter for a tool discovered on an MCP server.
func NewMCPTool(server Server, info ToolInfo) *MCPTool {
	namespacedName := fmt.Sprintf("%s__%s", server.Name(), info.Name)
	schemaStr := string(info.InputSchema)
	if schemaStr == "" || schemaStr == "null" {
		schemaStr = `{"type":"object"}`
	}

	risk := classifyRisk(info.Name, info.Description)

	return &MCPTool{
		server:         server,
		serverName:     server.Name(),
		originalName:   info.Name,
		namespacedName: namespacedName,
		description:    fmt.Sprintf("[%s] %s", server.Name(), info.Description),
		schema:         schemaStr,
		risk:           risk,
	}
}

// Metadata returns the tool specification required by the agent planning engine.
func (t *MCPTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               t.namespacedName,
		Category:           "mcp",
		Description:        t.description,
		ParameterSchema:    t.schema,
		PromptUsageTip:     fmt.Sprintf("External tool provided by %s MCP server.", t.serverName),
		Risk:               t.risk,
		RequiredCapability: fmt.Sprintf("mcp:%s", t.serverName),
	}
}

// Execute invokes the underlying MCP server tool via JSON-RPC.
func (t *MCPTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	args := make(map[string]any)
	if argsJSON != "" && argsJSON != "{}" {
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return &tools.ToolResult{
				IsError:  true,
				ExitCode: 1,
				Stderr:   fmt.Sprintf("invalid arguments for %s: %v", t.namespacedName, err),
			}, nil
		}
	}

	return t.server.CallTool(ctx, t.originalName, args)
}

func classifyRisk(name, description string) tools.RiskLevel {
	combined := name + " " + description
	highRiskKeywords := []string{"delete", "remove", "drop", "destroy", "kill", "terminate", "format", "purge", "execute"}
	if containsWord(combined, highRiskKeywords) {
		return tools.RiskHigh
	}

	lowRiskKeywords := []string{"get", "list", "read", "fetch", "search", "query", "find", "status", "check", "view"}
	if containsWord(combined, lowRiskKeywords) {
		return tools.RiskLow
	}

	return tools.RiskMedium
}

func containsWord(text string, targets []string) bool {
	words := strings.FieldsFunc(strings.ToLower(text), func(r rune) bool {
		return r == '_' || r == '-' || r == ' ' || r == '.' || r == ',' || r == ':' || r == '/' || r == '\\' || r == '(' || r == ')' || r == '[' || r == ']'
	})

	for _, w := range words {
		for _, t := range targets {
			if w == t {
				return true
			}
		}
	}
	return false
}

package mcp

import "encoding/json"

const (
	// DefaultProtocolVersion matches the standard MCP protocol release.
	DefaultProtocolVersion = "2024-11-05"

	// ClientName and ClientVersion identify this assistant to MCP servers.
	ClientName    = "ai-personal-assistant"
	ClientVersion = "1.0.0"
)

// JSONRPCRequest encapsulates a standard JSON-RPC 2.0 request payload.
type JSONRPCRequest struct {
	JSONRPC string `json:"jsonrpc"`
	ID      uint64 `json:"id"`
	Method  string `json:"method"`
	Params  any    `json:"params,omitempty"`
}

// JSONRPCResponse encapsulates a standard JSON-RPC 2.0 response payload.
type JSONRPCResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      uint64          `json:"id"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *JSONRPCError   `json:"error,omitempty"`
}

// JSONRPCError defines the standard error structure returned by JSON-RPC.
type JSONRPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    any    `json:"data,omitempty"`
}

// InitializeParams defines client metadata sent during MCP connection setup.
type InitializeParams struct {
	ProtocolVersion string             `json:"protocolVersion"`
	Capabilities    ClientCapabilities `json:"capabilities"`
	ClientInfo      ImplementationInfo `json:"clientInfo"`
}

// ClientCapabilities declares supported MCP client features.
type ClientCapabilities struct {
	Roots     *RootsCapability `json:"roots,omitempty"`
	Sampling  map[string]any   `json:"sampling,omitempty"`
}

// RootsCapability indicates whether the client can supply filesystem roots.
type RootsCapability struct {
	ListChanged bool `json:"listChanged"`
}

// ImplementationInfo identifies an MCP client or server.
type ImplementationInfo struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// ToolInfo describes a single executable tool exposed by an MCP server.
type ToolInfo struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	InputSchema json.RawMessage `json:"inputSchema"`
}

// ListToolsResult contains the array of tools returned by tools/list.
type ListToolsResult struct {
	Tools []ToolInfo `json:"tools"`
}

// CallToolParams specifies the target tool and arguments for tools/call.
type CallToolParams struct {
	Name      string         `json:"name"`
	Arguments map[string]any `json:"arguments,omitempty"`
}

// ContentItem represents an individual text or binary result block from a tool execution.
type ContentItem struct {
	Type string `json:"type"`
	Text string `json:"text,omitempty"`
}

// CallToolResult encapsulates the content blocks returned by tools/call.
type CallToolResult struct {
	Content []ContentItem `json:"content"`
	IsError bool          `json:"isError"`
}

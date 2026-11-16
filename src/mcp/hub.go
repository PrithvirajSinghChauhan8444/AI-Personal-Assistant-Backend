package mcp

import (
	"context"
	"fmt"
	"os"
	"sync"

	"assistant/src/tools"
)

// Hub manages the lifecycle of multiple MCP servers and coordinates tool registration.
type Hub struct {
	mu      sync.RWMutex
	servers map[string]Server
	tools   []tools.Tool
}

// NewHub initializes an MCP Hub from configuration.
func NewHub(cfg *Config) *Hub {
	hub := &Hub{
		servers: make(map[string]Server),
		tools:   make([]tools.Tool, 0),
	}

	if cfg == nil {
		return hub
	}

	for name, srvCfg := range cfg.MCPServers {
		if !srvCfg.IsEnabled() {
			continue
		}
		hub.servers[name] = NewStdioServer(name, srvCfg)
	}

	return hub
}

// AddServer registers an existing server instance into the Hub. Useful for testing and custom bridges.
func (h *Hub) AddServer(server Server) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.servers[server.Name()] = server
}

// StartAll launches and initializes all registered MCP servers concurrently.
func (h *Hub) StartAll(ctx context.Context) error {
	h.mu.Lock()
	defer h.mu.Unlock()

	var wg sync.WaitGroup
	var errMu sync.Mutex
	var startupErrors []error

	discoveredTools := make([]tools.Tool, 0)
	var toolsMu sync.Mutex

	for name, srv := range h.servers {
		wg.Add(1)
		go func(sName string, s Server) {
			defer wg.Done()

			if err := s.Start(ctx); err != nil {
				errMu.Lock()
				startupErrors = append(startupErrors, fmt.Errorf("server %q failed to start: %w", sName, err))
				errMu.Unlock()
				return
			}

			toolsList, err := s.ListTools(ctx)
			if err != nil {
				errMu.Lock()
				startupErrors = append(startupErrors, fmt.Errorf("server %q failed to list tools: %w", sName, err))
				errMu.Unlock()
				return
			}

			toolsMu.Lock()
			for _, info := range toolsList {
				discoveredTools = append(discoveredTools, NewMCPTool(s, info))
			}
			toolsMu.Unlock()
		}(name, srv)
	}

	wg.Wait()
	h.tools = discoveredTools

	if len(startupErrors) > 0 {
		for _, err := range startupErrors {
			_, _ = fmt.Fprintf(os.Stderr, "Warning: [MCP Hub] %v\n", err)
		}
	}

	return nil
}

// RegisterAllTools exposes all discovered MCP tools to the assistant's ToolRegistry.
func (h *Hub) RegisterAllTools(registry *tools.ToolRegistry) error {
	if registry == nil {
		return fmt.Errorf("cannot register tools into nil registry")
	}

	h.mu.RLock()
	defer h.mu.RUnlock()

	for _, t := range h.tools {
		if err := registry.Register(t); err != nil {
			return fmt.Errorf("failed to register MCP tool %q: %w", t.Metadata().Name, err)
		}
	}

	return nil
}

// Tools returns a snapshot of all active MCP tools.
func (h *Hub) Tools() []tools.Tool {
	h.mu.RLock()
	defer h.mu.RUnlock()

	result := make([]tools.Tool, len(h.tools))
	copy(result, h.tools)
	return result
}

// Close gracefully terminates all running MCP servers.
func (h *Hub) Close() {
	h.mu.Lock()
	defer h.mu.Unlock()

	for _, srv := range h.servers {
		_ = srv.Close()
	}
}

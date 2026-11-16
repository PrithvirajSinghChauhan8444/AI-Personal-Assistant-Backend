package mcp

import (
	"encoding/json"
	"fmt"
	"os"
)

// ServerConfig defines the execution parameters for an individual MCP server.
type ServerConfig struct {
	Command        string            `json:"command"`
	Args           []string          `json:"args"`
	Env            map[string]string `json:"env"`
	Enabled        *bool             `json:"enabled,omitempty"`
	TimeoutSeconds int               `json:"timeout_seconds,omitempty"`
}

// IsEnabled returns true if the server is enabled or if enabled is not specified.
func (c *ServerConfig) IsEnabled() bool {
	if c.Enabled == nil {
		return true
	}
	return *c.Enabled
}

// Config represents the root mcp_servers.json configuration file.
type Config struct {
	MCPServers map[string]ServerConfig `json:"mcpServers"`
}

// LoadConfigFile reads and parses an MCP configuration JSON file, expanding environment variables.
func LoadConfigFile(filePath string) (*Config, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read mcp configuration %q: %w", filePath, err)
	}

	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse mcp configuration: %w", err)
	}

	cfg.expandEnvironmentVariables()
	return &cfg, nil
}

// expandEnvironmentVariables resolves ${VAR} and $VAR placeholders in server configs.
func (c *Config) expandEnvironmentVariables() {
	for name, srv := range c.MCPServers {
		srv.Command = os.ExpandEnv(srv.Command)

		for i, arg := range srv.Args {
			srv.Args[i] = os.ExpandEnv(arg)
		}

		for k, v := range srv.Env {
			srv.Env[k] = os.ExpandEnv(v)
		}

		c.MCPServers[name] = srv
	}
}

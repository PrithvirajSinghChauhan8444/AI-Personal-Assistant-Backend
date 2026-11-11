package tools

import (
	"context"
	"database/sql"
	"fmt"
	"sync"
	"time"
)

// RegisteredTool binds an executable tool to its runtime enabled toggle.
type RegisteredTool struct {
	Tool    Tool
	Enabled bool
}

// ToolRegistry manages thread-safe tool discovery, live toggling, and native execution.
type ToolRegistry struct {
	mu        sync.RWMutex
	tools     map[string]*RegisteredTool
	db        *sql.DB
	spillover *SpilloverManager
}

// NewToolRegistry constructs a ToolRegistry backed by an optional SQLite database and spillover manager.
func NewToolRegistry(db *sql.DB, spillover *SpilloverManager) *ToolRegistry {
	if spillover == nil {
		spillover = NewSpilloverManager("", 0)
	}

	registry := &ToolRegistry{
		tools:     make(map[string]*RegisteredTool),
		db:        db,
		spillover: spillover,
	}

	if db != nil {
		_ = registry.InitSchema()
	}

	return registry
}

// InitSchema ensures the persistence tables exist in SQLite.
func (r *ToolRegistry) InitSchema() error {
	if r.db == nil {
		return nil
	}

	schema := `
	CREATE TABLE IF NOT EXISTS tool_configs (
		tool_name TEXT PRIMARY KEY,
		enabled BOOLEAN NOT NULL DEFAULT 1,
		updated_at TIMESTAMP NOT NULL
	);
	CREATE TABLE IF NOT EXISTS tool_audit_log (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL,
		turn_id TEXT NOT NULL,
		tool_name TEXT NOT NULL,
		risk_level TEXT NOT NULL,
		status TEXT NOT NULL,
		duration_ms INTEGER NOT NULL,
		created_at TIMESTAMP NOT NULL
	);`

	_, err := r.db.Exec(schema)
	if err != nil {
		return fmt.Errorf("failed to initialize tool schema: %w", err)
	}
	return nil
}

// Register registers a tool into the active catalog, loading saved toggle states if present.
func (r *ToolRegistry) Register(tool Tool) error {
	if tool == nil {
		return fmt.Errorf("cannot register nil tool")
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	meta := tool.Metadata()
	if meta.Name == "" {
		return fmt.Errorf("tool name cannot be empty")
	}

	enabled := true
	if r.db != nil {
		var dbEnabled bool
		query := "SELECT enabled FROM tool_configs WHERE tool_name = ?"
		if err := r.db.QueryRow(query, meta.Name).Scan(&dbEnabled); err == nil {
			enabled = dbEnabled
		}
	}

	r.tools[meta.Name] = &RegisteredTool{
		Tool:    tool,
		Enabled: enabled,
	}
	return nil
}

// SetToolStatus toggles a tool online or offline at runtime and updates SQLite.
func (r *ToolRegistry) SetToolStatus(toolName string, enabled bool) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	reg, exists := r.tools[toolName]
	if !exists {
		return fmt.Errorf("tool %q not registered", toolName)
	}

	reg.Enabled = enabled

	if r.db != nil {
		query := `
		INSERT INTO tool_configs (tool_name, enabled, updated_at)
		VALUES (?, ?, CURRENT_TIMESTAMP)
		ON CONFLICT(tool_name) DO UPDATE SET enabled = excluded.enabled, updated_at = CURRENT_TIMESTAMP`
		if _, err := r.db.Exec(query, toolName, enabled); err != nil {
			return fmt.Errorf("failed to persist tool status: %w", err)
		}
	}

	return nil
}

// SetToolEnabled is an alias for SetToolStatus.
func (r *ToolRegistry) SetToolEnabled(toolName string, enabled bool) error {
	return r.SetToolStatus(toolName, enabled)
}

// IsToolEnabled queries the live operational state of a tool.
func (r *ToolRegistry) IsToolEnabled(toolName string) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()

	reg, exists := r.tools[toolName]
	return exists && reg.Enabled
}

// GetTool retrieves a registered tool instance.
func (r *ToolRegistry) GetTool(toolName string) (Tool, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	reg, exists := r.tools[toolName]
	if !exists {
		return nil, false
	}
	return reg.Tool, true
}

// GetActiveTools returns metadata for enabled tools, filtered by granted capabilities.
func (r *ToolRegistry) GetActiveTools(allowedCaps []string) []ToolMetadata {
	r.mu.RLock()
	defer r.mu.RUnlock()

	capFilter := buildCapabilityFilter(allowedCaps)
	activeTools := make([]ToolMetadata, 0, len(r.tools))

	for _, reg := range r.tools {
		if !reg.Enabled {
			continue
		}

		meta := reg.Tool.Metadata()
		if len(allowedCaps) > 0 && meta.RequiredCapability != "" && !capFilter[meta.RequiredCapability] {
			continue
		}

		activeTools = append(activeTools, meta)
	}

	return activeTools
}

// Execute invokes a tool with standard context and default empty identifiers.
func (r *ToolRegistry) Execute(ctx context.Context, toolName string, argsJSON string) (*ToolResult, error) {
	return r.ExecuteWithContext(ctx, "", "", "", toolName, argsJSON)
}

// ExecuteWithContext executes a tool within an audited session frame with automatic spillover.
func (r *ToolRegistry) ExecuteWithContext(ctx context.Context, sessionID, turnID, callID, toolName, argsJSON string) (*ToolResult, error) {
	tool, risk, err := r.resolveToolForExecution(toolName)
	if err != nil {
		return &ToolResult{
			CallID:   callID,
			IsError:  true,
			ExitCode: 1,
			Stderr:   err.Error(),
		}, nil
	}

	startTime := time.Now()
	res, execErr := tool.Execute(ctx, argsJSON)
	duration := time.Since(startTime).Milliseconds()

	if res == nil {
		res = &ToolResult{
			CallID:     callID,
			IsError:    true,
			ExitCode:   1,
			Stderr:     "tool returned nil result",
			DurationMs: duration,
		}
	} else {
		res.CallID = callID
		res.DurationMs = duration
	}

	if execErr != nil {
		res.IsError = true
		if res.Stderr == "" {
			res.Stderr = execErr.Error()
		}
	}

	r.applyOutputSpillover(res)
	r.recordAuditLog(sessionID, turnID, toolName, risk, res)

	return res, execErr
}

func (r *ToolRegistry) resolveToolForExecution(toolName string) (Tool, RiskLevel, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	reg, exists := r.tools[toolName]
	if !exists {
		return nil, "", fmt.Errorf("tool %q does not exist in registry", toolName)
	}

	if !reg.Enabled {
		return nil, "", fmt.Errorf("tool %q is currently disabled by user", toolName)
	}

	return reg.Tool, reg.Tool.Metadata().Risk, nil
}

func (r *ToolRegistry) applyOutputSpillover(res *ToolResult) {
	if r.spillover == nil || res.Stdout == "" {
		return
	}

	preview, artifactPath, spilled, err := r.spillover.Process(res.Stdout)
	if err == nil && spilled {
		res.Stdout = preview
		res.ArtifactPath = artifactPath
	}
}

func (r *ToolRegistry) recordAuditLog(sessionID, turnID, toolName string, risk RiskLevel, res *ToolResult) {
	if r.db == nil || sessionID == "" {
		return
	}

	status := "SUCCESS"
	if res.IsError {
		status = "FAILED"
	}

	query := `
	INSERT INTO tool_audit_log (session_id, turn_id, tool_name, risk_level, status, duration_ms, created_at)
	VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)`
	_, _ = r.db.Exec(query, sessionID, turnID, toolName, string(risk), status, res.DurationMs)
}

func buildCapabilityFilter(caps []string) map[string]bool {
	filter := make(map[string]bool, len(caps))
	for _, capName := range caps {
		filter[capName] = true
	}
	return filter
}

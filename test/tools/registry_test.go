package tools_test

import (
	"context"
	"database/sql"
	"fmt"
	"path/filepath"
	"testing"
	"time"

	"assistant/src/tools"

	_ "modernc.org/sqlite"
)

type dummyTool struct {
	name string
	risk tools.RiskLevel
	cap  string
}

func (d *dummyTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               d.name,
		Category:           "test",
		Description:        "dummy test tool",
		Risk:               d.risk,
		RequiredCapability: d.cap,
	}
}

func (d *dummyTool) Execute(_ context.Context, argsJSON string) (*tools.ToolResult, error) {
	return &tools.ToolResult{
		Stdout:   fmt.Sprintf("executed %s with %s", d.name, argsJSON),
		ExitCode: 0,
		IsError:  false,
	}, nil
}

func TestToolRegistryLifecycleAndToggling(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "test_sessions.db")

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatalf("failed to open sqlite: %v", err)
	}
	defer db.Close()

	reg := tools.NewToolRegistry(db, nil)

	tool1 := &dummyTool{name: "tool_alpha", risk: tools.RiskLow, cap: "alpha:read"}
	tool2 := &dummyTool{name: "tool_beta", risk: tools.RiskHigh, cap: "beta:write"}

	if err := reg.Register(tool1); err != nil {
		t.Fatalf("failed to register tool1: %v", err)
	}
	if err := reg.Register(tool2); err != nil {
		t.Fatalf("failed to register tool2: %v", err)
	}

	if !reg.IsToolEnabled("tool_alpha") || !reg.IsToolEnabled("tool_beta") {
		t.Fatalf("expected both tools to be enabled initially")
	}

	activeAll := reg.GetActiveTools(nil)
	if len(activeAll) != 2 {
		t.Fatalf("expected 2 active tools, got %d", len(activeAll))
	}

	activeFiltered := reg.GetActiveTools([]string{"alpha:read"})
	if len(activeFiltered) != 1 || activeFiltered[0].Name != "tool_alpha" {
		t.Fatalf("expected 1 active tool matching cap 'alpha:read', got %d", len(activeFiltered))
	}

	// Disable tool_beta
	if err := reg.SetToolStatus("tool_beta", false); err != nil {
		t.Fatalf("failed to disable tool_beta: %v", err)
	}

	if reg.IsToolEnabled("tool_beta") {
		t.Fatalf("expected tool_beta to be disabled")
	}

	activeAfterToggle := reg.GetActiveTools(nil)
	if len(activeAfterToggle) != 1 || activeAfterToggle[0].Name != "tool_alpha" {
		t.Fatalf("expected only tool_alpha active after disabling tool_beta")
	}

	// Execute disabled tool should fail with disabled message
	res, err := reg.Execute(context.Background(), "tool_beta", "{}")
	if err != nil {
		t.Fatalf("execute should return ToolResult with error flag: %v", err)
	}
	if !res.IsError || res.ExitCode != 1 {
		t.Errorf("expected error on executing disabled tool")
	}

	// Verify persistence in SQLite across a new registry instance
	newReg := tools.NewToolRegistry(db, nil)
	_ = newReg.Register(tool2)
	if newReg.IsToolEnabled("tool_beta") {
		t.Fatalf("expected tool_beta disabled state to persist across registry instances")
	}
}

func TestToolRegistryTelemetryLogging(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "test_telemetry.db")

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatalf("failed to open sqlite: %v", err)
	}
	defer db.Close()

	reg := tools.NewToolRegistry(db, nil)
	tool := &dummyTool{name: "telemetry_tool", risk: tools.RiskMedium, cap: "sys:read"}
	_ = reg.Register(tool)

	sessionID := "sess_001"
	turnID := "turn_001"
	callID := "call_001"

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	res, err := reg.ExecuteWithContext(ctx, sessionID, turnID, callID, "telemetry_tool", `{"ping":"pong"}`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if res.CallID != callID || res.IsError {
		t.Fatalf("unexpected execution result: %+v", res)
	}

	// Verify entry in tool_audit_log
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM tool_audit_log WHERE session_id = ? AND tool_name = ?", sessionID, "telemetry_tool").Scan(&count)
	if err != nil {
		t.Fatalf("failed querying tool_audit_log: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 audit log record, got %d", count)
	}
}

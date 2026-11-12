package tools_test

import (
	"context"
	"testing"

	"assistant/src/tools/dispatcher"
	"assistant/src/tools"
)

func TestBrowserToolsRegistration(t *testing.T) {
	registry := tools.NewToolRegistry(nil, nil)
	if err := dispatcher.RegisterAllTools(registry, "config"); err != nil {
		t.Fatalf("RegisterAllTools failed: %v", err)
	}

	requiredTools := []string{
		"browser_navigate",
		"browser_snapshot",
		"browser_read_content",
		"browser_click",
		"browser_type",
		"browser_take_screenshot",
		"browser_screenshot",
		"browser_tabs",
		"browser_wait_for",
		"browser_navigate_back",
		"browser_close",
	}

	for _, name := range requiredTools {
		tool, exists := registry.GetTool(name)
		if !exists || tool == nil {
			t.Errorf("expected tool %q to be registered in ToolRegistry, but got exists=%v", name, exists)
		}
		if !registry.IsToolEnabled(name) {
			t.Errorf("expected tool %q to be enabled by default", name)
		}
	}
}

func TestBrowserNavigateInvalidJSON(t *testing.T) {
	registry := tools.NewToolRegistry(nil, nil)
	_ = dispatcher.RegisterAllTools(registry, "config")

	tool, exists := registry.GetTool("browser_navigate")
	if !exists || tool == nil {
		t.Fatal("browser_navigate tool not found")
	}

	res, err := tool.Execute(context.Background(), "{invalid-json")
	if err != nil {
		t.Fatalf("unexpected execution error: %v", err)
	}
	if !res.IsError {
		t.Errorf("expected IsError to be true for invalid json, got false")
	}
}

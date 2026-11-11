package tools_test

import (
	"encoding/json"
	"testing"

	"assistant/src/tools"
)

func TestToolMetadataJSONSerialization(t *testing.T) {
	meta := tools.ToolMetadata{
		Name:               "test_tool",
		Category:           "filesystem",
		Description:        "A test tool",
		ParameterSchema:    `{"type":"object"}`,
		PromptUsageTip:     "Use for testing",
		Risk:               tools.RiskLow,
		RequiredCapability: "fs:read",
	}

	data, err := json.Marshal(meta)
	if err != nil {
		t.Fatalf("failed to marshal ToolMetadata: %v", err)
	}

	var decoded tools.ToolMetadata
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("failed to unmarshal ToolMetadata: %v", err)
	}

	if decoded.Name != meta.Name || decoded.Risk != tools.RiskLow || decoded.RequiredCapability != "fs:read" {
		t.Fatalf("mismatched decoded metadata: %+v", decoded)
	}
}

func TestToolResultJSONSerialization(t *testing.T) {
	res := tools.ToolResult{
		CallID:       "call_123",
		Stdout:       "all good",
		Stderr:       "",
		ExitCode:     0,
		IsError:      false,
		DurationMs:   42,
		ArtifactPath: "/tmp/art.txt",
	}

	data, err := json.Marshal(res)
	if err != nil {
		t.Fatalf("failed to marshal ToolResult: %v", err)
	}

	var decoded tools.ToolResult
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("failed to unmarshal ToolResult: %v", err)
	}

	if decoded.CallID != "call_123" || decoded.ExitCode != 0 || decoded.DurationMs != 42 || decoded.ArtifactPath != "/tmp/art.txt" {
		t.Fatalf("mismatched decoded result: %+v", decoded)
	}
}

func TestRiskLevelConstants(t *testing.T) {
	if tools.RiskLow != "LOW" {
		t.Errorf("expected RiskLow to be LOW, got %s", tools.RiskLow)
	}
	if tools.RiskMedium != "MEDIUM" {
		t.Errorf("expected RiskMedium to be MEDIUM, got %s", tools.RiskMedium)
	}
	if tools.RiskHigh != "HIGH" {
		t.Errorf("expected RiskHigh to be HIGH, got %s", tools.RiskHigh)
	}
}

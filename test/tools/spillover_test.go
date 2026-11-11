package tools_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"assistant/src/tools"
)

func TestSpilloverBelowThreshold(t *testing.T) {
	tempDir := t.TempDir()
	sm := tools.NewSpilloverManager(tempDir, 1024)

	input := "short payload within limits"
	output, artifactPath, spilled, err := sm.Process(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if spilled {
		t.Errorf("expected spilled=false for payload below threshold")
	}
	if artifactPath != "" {
		t.Errorf("expected empty artifact path, got %q", artifactPath)
	}
	if output != input {
		t.Errorf("expected output to match input")
	}
}

func TestSpilloverExceedingThreshold(t *testing.T) {
	tempDir := t.TempDir()
	threshold := 500
	sm := tools.NewSpilloverManager(tempDir, threshold)

	lines := make([]string, 100)
	for i := 0; i < 100; i++ {
		lines[i] = "line of text to exceed the threshold limit"
	}
	largePayload := strings.Join(lines, "\n")

	output, artifactPath, spilled, err := sm.Process(largePayload)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !spilled {
		t.Fatalf("expected spilled=true for payload exceeding threshold")
	}

	if artifactPath == "" {
		t.Fatalf("expected non-empty artifact path")
	}

	diskData, err := os.ReadFile(artifactPath)
	if err != nil {
		t.Fatalf("failed reading spilled file: %v", err)
	}

	if string(diskData) != largePayload {
		t.Fatalf("spilled content does not match original payload")
	}

	if !strings.Contains(output, "[Output truncated") {
		t.Errorf("expected truncation notice in output preview")
	}

	if !strings.Contains(output, filepath.Base(artifactPath)) {
		t.Errorf("expected artifact filename in preview notice")
	}
}

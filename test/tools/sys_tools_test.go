package tools_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"assistant/src/tools/tools/sys"
)

func TestSysExecToolSuccess(t *testing.T) {
	tool := sys.NewSysExecTool()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	res, err := tool.Execute(ctx, `{"command":"echo 'hello clean code'"}`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if res.IsError || res.ExitCode != 0 {
		t.Fatalf("expected success, got exit %d: %s", res.ExitCode, res.Stderr)
	}

	if !strings.Contains(res.Stdout, "hello clean code") {
		t.Errorf("expected stdout to contain 'hello clean code', got: %s", res.Stdout)
	}
}

func TestSysExecToolCwd(t *testing.T) {
	tempDir := t.TempDir()
	tool := sys.NewSysExecTool()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	res, err := tool.Execute(ctx, `{"command":"pwd","cwd":"`+tempDir+`"}`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if res.IsError || res.ExitCode != 0 {
		t.Fatalf("expected success, got: %s", res.Stderr)
	}

	if !strings.Contains(strings.TrimSpace(res.Stdout), tempDir) {
		t.Errorf("expected pwd to return %q, got: %s", tempDir, res.Stdout)
	}
}

func TestSysExecToolTimeout(t *testing.T) {
	tool := sys.NewSysExecTool()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	res, err := tool.Execute(ctx, `{"command":"sleep 10","timeout_seconds":1}`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !res.IsError || res.ExitCode == 0 {
		t.Errorf("expected timeout execution failure")
	}
}

func TestSysPsTool(t *testing.T) {
	tool := sys.NewSysPsTool()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	res, err := tool.Execute(ctx, `{"limit":10}`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if res.IsError || res.ExitCode != 0 {
		t.Fatalf("expected success, got: %s", res.Stderr)
	}

	if !strings.Contains(res.Stdout, "PID") {
		t.Errorf("expected ps output header with PID, got: %s", res.Stdout)
	}
}

func TestSysKillToolProtectedPID(t *testing.T) {
	tool := sys.NewSysKillTool()
	ctx := context.Background()

	res, err := tool.Execute(ctx, `{"pid":1,"signal":"SIGTERM"}`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !res.IsError || !strings.Contains(res.Stderr, "protected") {
		t.Errorf("expected refusal to signal PID 1")
	}
}

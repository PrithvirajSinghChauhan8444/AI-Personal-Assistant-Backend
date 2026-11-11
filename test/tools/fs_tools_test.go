package tools_test

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"assistant/src/tools/tools/fs"
)

func TestFsWriteAndRead(t *testing.T) {
	tempDir := t.TempDir()
	filePath := filepath.Join(tempDir, "subdir", "test.txt")

	writeTool := fs.NewFsWriteTool()
	readTool := fs.NewFsReadTool()
	ctx := context.Background()

	content := "Line 1: Clean Code\nLine 2: Layer 3 Tool Engine\nLine 3: Sub-5ms latency\nLine 4: Autonomous turn\nLine 5: Verification"

	// Test atomic write with directory creation
	writeArgs := `{"path":"` + filePath + `","content":` + quoteJSON(content) + `}`
	writeRes, err := writeTool.Execute(ctx, writeArgs)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if writeRes.IsError || writeRes.ExitCode != 0 {
		t.Fatalf("write failed: %s", writeRes.Stderr)
	}

	// Test full read
	readArgs := `{"path":"` + filePath + `"}`
	readRes, err := readTool.Execute(ctx, readArgs)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if readRes.Stdout != content {
		t.Fatalf("read content mismatch: expected %q, got %q", content, readRes.Stdout)
	}

	// Test line slicing (lines 2 to 4)
	sliceArgs := `{"path":"` + filePath + `","start_line":2,"end_line":4}`
	sliceRes, err := readTool.Execute(ctx, sliceArgs)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expectedSlice := "Line 2: Layer 3 Tool Engine\nLine 3: Sub-5ms latency\nLine 4: Autonomous turn"
	if sliceRes.Stdout != expectedSlice {
		t.Fatalf("line slice mismatch: expected %q, got %q", expectedSlice, sliceRes.Stdout)
	}

	// Test append
	appendArgs := `{"path":"` + filePath + `","content":"\nLine 6: Appended","append":true}`
	_, _ = writeTool.Execute(ctx, appendArgs)

	readAfterAppend, _ := readTool.Execute(ctx, readArgs)
	if !strings.Contains(readAfterAppend.Stdout, "Line 6: Appended") {
		t.Fatalf("expected appended content in file")
	}
}

func TestFsDeleteAndList(t *testing.T) {
	tempDir := t.TempDir()
	file1 := filepath.Join(tempDir, "file1.txt")
	file2 := filepath.Join(tempDir, "sub", "file2.txt")
	_ = os.MkdirAll(filepath.Dir(file2), 0755)
	_ = os.WriteFile(file1, []byte("data1"), 0644)
	_ = os.WriteFile(file2, []byte("data2"), 0644)

	listTool := fs.NewFsListTool()
	deleteTool := fs.NewFsDeleteTool()
	ctx := context.Background()

	// Test list
	listArgs := `{"path":"` + tempDir + `","recursive":true,"max_depth":3}`
	listRes, err := listTool.Execute(ctx, listArgs)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(listRes.Stdout, "file1.txt") || !strings.Contains(listRes.Stdout, "file2.txt") {
		t.Fatalf("expected listing to show file1 and file2: %s", listRes.Stdout)
	}

	// Test delete single file
	delFileArgs := `{"path":"` + file1 + `"}`
	delRes, err := deleteTool.Execute(ctx, delFileArgs)
	if err != nil || delRes.IsError {
		t.Fatalf("delete file failed: %v: %s", err, delRes.Stderr)
	}

	// Test delete directory recursive
	delDirArgs := `{"path":"` + filepath.Join(tempDir, "sub") + `","recursive":true}`
	delDirRes, err := deleteTool.Execute(ctx, delDirArgs)
	if err != nil || delDirRes.IsError {
		t.Fatalf("delete dir failed: %v: %s", err, delDirRes.Stderr)
	}

	// Test delete root rejected
	delRootArgs := `{"path":"/"}`
	delRootRes, _ := deleteTool.Execute(ctx, delRootArgs)
	if !delRootRes.IsError {
		t.Fatalf("expected delete '/' to be rejected")
	}
}

func TestFsRipgrep(t *testing.T) {
	tempDir := t.TempDir()
	testFile := filepath.Join(tempDir, "code.go")
	_ = os.WriteFile(testFile, []byte("package main\n\nfunc CleanCodeMagic() string {\n\treturn \"clean\"\n}\n"), 0644)

	rgTool := fs.NewFsRipgrepTool()
	ctx := context.Background()

	res, err := rgTool.Execute(ctx, `{"query":"CleanCodeMagic","path":"`+tempDir+`"}`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.IsError || !strings.Contains(res.Stdout, "CleanCodeMagic") {
		t.Fatalf("expected ripgrep to find CleanCodeMagic: %s", res.Stdout)
	}
}

func quoteJSON(s string) string {
	escaped := strings.ReplaceAll(s, "\\", "\\\\")
	escaped = strings.ReplaceAll(escaped, "\"", "\\\"")
	escaped = strings.ReplaceAll(escaped, "\n", "\\n")
	escaped = strings.ReplaceAll(escaped, "\t", "\\t")
	escaped = strings.ReplaceAll(escaped, "\r", "\\r")
	return "\"" + escaped + "\""
}

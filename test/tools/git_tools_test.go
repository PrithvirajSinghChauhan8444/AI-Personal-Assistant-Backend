package tools_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"assistant/src/tools/tools/git"
)

func setupTestGitRepo(t *testing.T) string {
	tempDir := t.TempDir()

	runGit(t, tempDir, "init")
	runGit(t, tempDir, "config", "user.name", "Tester")
	runGit(t, tempDir, "config", "user.email", "tester@example.com")

	dummyFile := filepath.Join(tempDir, "hello.txt")
	if err := os.WriteFile(dummyFile, []byte("first commit"), 0644); err != nil {
		t.Fatalf("failed creating initial file: %v", err)
	}

	runGit(t, tempDir, "add", "hello.txt")
	runGit(t, tempDir, "commit", "-m", "initial commit")

	return tempDir
}

func runGit(t *testing.T, dir string, args ...string) {
	cmd := exec.Command("git", args...)
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("git %s failed: %v: %s", strings.Join(args, " "), err, string(out))
	}
}

func TestGitStatusAndDiffAndCommit(t *testing.T) {
	repoDir := setupTestGitRepo(t)
	statusTool := git.NewGitStatusTool()
	diffTool := git.NewGitDiffTool()
	commitTool := git.NewGitCommitTool()
	ctx := context.Background()

	// Initial status (clean)
	statusRes, err := statusTool.Execute(ctx, `{"repo_path":"`+repoDir+`"}`)
	if err != nil || statusRes.IsError {
		t.Fatalf("git_status failed: %v: %s", err, statusRes.Stderr)
	}

	// Modify file
	modFile := filepath.Join(repoDir, "hello.txt")
	_ = os.WriteFile(modFile, []byte("second commit changes"), 0644)

	// Check diff
	diffRes, err := diffTool.Execute(ctx, `{"repo_path":"`+repoDir+`"}`)
	if err != nil || diffRes.IsError {
		t.Fatalf("git_diff failed: %v: %s", err, diffRes.Stderr)
	}
	if !strings.Contains(diffRes.Stdout, "+second commit changes") {
		t.Fatalf("expected git_diff to show additions: %s", diffRes.Stdout)
	}

	// Commit changes
	commitRes, err := commitTool.Execute(ctx, `{"repo_path":"`+repoDir+`","message":"feat: second commit"}`)
	if err != nil || commitRes.IsError {
		t.Fatalf("git_commit failed: %v: %s", err, commitRes.Stderr)
	}

	// Verify status after commit
	cleanStatus, _ := statusTool.Execute(ctx, `{"repo_path":"`+repoDir+`"}`)
	if strings.Contains(cleanStatus.Stdout, " M hello.txt") {
		t.Fatalf("expected clean working tree after commit")
	}
}

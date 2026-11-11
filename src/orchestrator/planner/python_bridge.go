package planner

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// PythonManagerBridge delegates planning and reasoning to the Layer 2 Python Manager Agent.
type PythonManagerBridge struct {
	pythonBinary  string
	managerScript string
}

// NewPythonManagerBridge discovers python runtime and creates the bridge.
func NewPythonManagerBridge(pythonBinary, managerScript string) *PythonManagerBridge {
	if pythonBinary == "" {
		pythonBinary = findPythonBinary()
	}
	if managerScript == "" {
		managerScript = findManagerScript()
	}
	return &PythonManagerBridge{
		pythonBinary:  pythonBinary,
		managerScript: managerScript,
	}
}

// Generate implements the LLMCaller interface by invoking the Python Manager in raw LLM mode.
func (p *PythonManagerBridge) Generate(ctx context.Context, systemPrompt, userPrompt string) (string, error) {
	if p.pythonBinary == "" {
		return "", errors.New("python runtime binary not found on system")
	}

	root := findProjectRoot()
	cmd := exec.CommandContext(ctx, p.pythonBinary, p.managerScript, "--raw-llm")
	cmd.Dir = root
	env := os.Environ()
	env = append(env, "PYTHONPATH="+root)
	cmd.Env = env

	payload := map[string]string{
		"system": systemPrompt,
		"user":   userPrompt,
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	cmd.Stdin = bytes.NewReader(payloadBytes)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("python manager process error: %w (stderr: %s)", err, strings.TrimSpace(stderr.String()))
	}

	return stdout.String(), nil
}

// Plan invokes the Python Manager directly to decompose the goal into an actionable TaskPlan DAG.
func (p *PythonManagerBridge) Plan(ctx context.Context, goal string, contextData map[string]interface{}) (*TaskPlan, error) {
	if p.pythonBinary == "" {
		return nil, errors.New("python runtime binary not found on system")
	}

	root := findProjectRoot()
	cmd := exec.CommandContext(ctx, p.pythonBinary, p.managerScript)
	cmd.Dir = root
	env := os.Environ()
	env = append(env, "PYTHONPATH="+root)
	cmd.Env = env

	payload := map[string]interface{}{
		"goal":    goal,
		"context": contextData,
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal plan input: %w", err)
	}

	cmd.Stdin = bytes.NewReader(payloadBytes)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("python manager execution failed: %w (stderr: %s)", err, strings.TrimSpace(stderr.String()))
	}

	cleanJSON := extractJSON(stdout.String())
	var plan TaskPlan
	if err := json.Unmarshal([]byte(cleanJSON), &plan); err != nil {
		return nil, fmt.Errorf("failed to parse task plan json: %w (raw: %s)", err, stdout.String())
	}

	return &plan, nil
}

// findProjectRoot locates the repository root containing go.mod.
func findProjectRoot() string {
	dir, err := os.Getwd()
	if err != nil {
		return "."
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return "."
}

// findPythonBinary searches for the virtual environment python first, then PATH binaries.
func findPythonBinary() string {
	root := findProjectRoot()
	candidates := []string{
		filepath.Join(root, ".venv", "bin", "python"),
		filepath.Join(root, ".venv", "bin", "python3"),
		filepath.Join(".venv", "bin", "python"),
		filepath.Join(".venv", "bin", "python3"),
		filepath.Join("..", ".venv", "bin", "python"),
	}

	for _, c := range candidates {
		if fi, err := os.Stat(c); err == nil && !fi.IsDir() {
			return c
		}
	}

	for _, name := range []string{"python3", "python"} {
		if path, err := exec.LookPath(name); err == nil {
			return path
		}
	}

	return ""
}

// findManagerScript locates the Layer 2 Manager package or entry point.
func findManagerScript() string {
	root := findProjectRoot()
	candidates := []string{
		filepath.Join(root, "src", "orchestrator", "manager", "manager.py"),
		filepath.Join(root, "src", "orchestrator", "manager", "__main__.py"),
		filepath.Join(root, "src", "orchestrator", "manager"),
		filepath.Join("src", "orchestrator", "manager", "manager.py"),
		filepath.Join("src", "orchestrator", "manager", "__main__.py"),
		filepath.Join("src", "orchestrator", "manager"),
	}

	for _, c := range candidates {
		if fi, err := os.Stat(c); err == nil {
			if !fi.IsDir() || c == filepath.Join(root, "src", "orchestrator", "manager") || c == filepath.Join("src", "orchestrator", "manager") {
				return c
			}
		}
	}

	return filepath.Join(root, "src", "orchestrator", "manager", "__main__.py")
}

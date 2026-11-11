package supervisor

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"
)

var (
	ErrProcessAlreadyRunning = errors.New("process is already running")
	ErrProcessNotRunning     = errors.New("process is not running")
	ErrPythonBinaryNotFound  = errors.New("python binary not found")
)

// ProcessConfig configures the Python daemon child process.
type ProcessConfig struct {
	PythonBinary string
	ModulePath   string
	WorkingDir   string
	ExtraArgs    []string
	Env          []string
}

// ProcessManager manages the lifecycle of the Python resident daemon.
type ProcessManager struct {
	cfg     ProcessConfig
	mu      sync.Mutex
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	stdout  io.ReadCloser
	stderr  io.ReadCloser
	running bool
}

// NewProcessManager constructs a ProcessManager with discovered or provided configurations.
func NewProcessManager(cfg ProcessConfig) *ProcessManager {
	root := findProjectRoot()
	if cfg.WorkingDir == "" {
		cfg.WorkingDir = root
	}
	if cfg.PythonBinary == "" {
		cfg.PythonBinary = findPythonBinary(root)
	}
	if cfg.ModulePath == "" {
		cfg.ModulePath = "src.bridge.daemon"
	}
	return &ProcessManager{
		cfg: cfg,
	}
}

// Start launches the child process and binds standard input/output pipes.
func (p *ProcessManager) Start(ctx context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.running {
		return ErrProcessAlreadyRunning
	}
	if p.cfg.PythonBinary == "" {
		return ErrPythonBinaryNotFound
	}

	args := []string{"-m", p.cfg.ModulePath}
	if len(p.cfg.ExtraArgs) > 0 {
		args = append(args, p.cfg.ExtraArgs...)
	}

	cmd := exec.CommandContext(ctx, p.cfg.PythonBinary, args...)
	if p.cfg.WorkingDir != "" {
		cmd.Dir = p.cfg.WorkingDir
	}

	env := os.Environ()
	if p.cfg.WorkingDir != "" {
		env = append(env, "PYTHONPATH="+p.cfg.WorkingDir)
	}
	if len(p.cfg.Env) > 0 {
		env = append(env, p.cfg.Env...)
	}
	cmd.Env = env

	stdinPipe, err := cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdin pipe: %w", err)
	}

	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		_ = stdinPipe.Close()
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		_ = stdinPipe.Close()
		_ = stdoutPipe.Close()
		return fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		_ = stdinPipe.Close()
		_ = stdoutPipe.Close()
		_ = stderrPipe.Close()
		return fmt.Errorf("failed to start python daemon: %w", err)
	}

	p.cmd = cmd
	p.stdin = stdinPipe
	p.stdout = stdoutPipe
	p.stderr = stderrPipe
	p.running = true

	return nil
}

// Stdin returns the write pipe connected to the child process's standard input.
func (p *ProcessManager) Stdin() io.WriteCloser {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.stdin
}

// Stdout returns the read pipe connected to the child process's standard output.
func (p *ProcessManager) Stdout() io.ReadCloser {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.stdout
}

// Stderr returns the read pipe connected to the child process's standard error.
func (p *ProcessManager) Stderr() io.ReadCloser {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.stderr
}

// IsRunning reports whether the supervised child process is active.
func (p *ProcessManager) IsRunning() bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.running
}

// Stop cleanly terminates the child process by closing stdin, ensuring zero orphan processes.
func (p *ProcessManager) Stop(gracePeriod time.Duration) error {
	p.mu.Lock()
	if !p.running || p.cmd == nil {
		p.mu.Unlock()
		return nil
	}

	// Close stdin pipe to signal EOF to the child daemon
	if p.stdin != nil {
		_ = p.stdin.Close()
	}
	cmd := p.cmd
	p.mu.Unlock()

	// Wait for clean exit within grace period
	done := make(chan error, 1)
	go func() {
		done <- cmd.Wait()
	}()

	select {
	case err := <-done:
		p.markStopped()
		return err
	case <-time.After(gracePeriod):
		// Force kill if child did not exit cleanly
		if cmd.Process != nil {
			_ = cmd.Process.Kill()
		}
		<-done
		p.markStopped()
		return errors.New("process killed after grace period expired")
	}
}

func (p *ProcessManager) markStopped() {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.running = false
	p.stdin = nil
	p.stdout = nil
	p.stderr = nil
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

// findPythonBinary searches virtual environments and PATH for a python executable.
func findPythonBinary(root string) string {
	candidates := []string{
		filepath.Join(root, ".venv", "bin", "python"),
		filepath.Join(root, ".venv", "bin", "python3"),
		filepath.Join(".venv", "bin", "python"),
		filepath.Join(".venv", "bin", "python3"),
		filepath.Join("..", ".venv", "bin", "python"),
		filepath.Join("..", ".venv", "bin", "python3"),
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

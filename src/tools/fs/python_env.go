package fs

import (
	"os"
	"os/exec"
	"path/filepath"
)

// resolveRepoRoot finds the project root containing go.mod.
func resolveRepoRoot() string {
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

// resolvePythonBinary finds the virtual environment python or falls back to system python.
func resolvePythonBinary() (string, string) {
	repoRoot := resolveRepoRoot()

	venvPython := filepath.Join(repoRoot, ".venv", "bin", "python")
	if _, err := os.Stat(venvPython); err == nil {
		return venvPython, repoRoot
	}

	venvPython3 := filepath.Join(repoRoot, ".venv", "bin", "python3")
	if _, err := os.Stat(venvPython3); err == nil {
		return venvPython3, repoRoot
	}

	if sysPython, err := exec.LookPath("python3"); err == nil {
		return sysPython, repoRoot
	}

	return "python3", repoRoot
}

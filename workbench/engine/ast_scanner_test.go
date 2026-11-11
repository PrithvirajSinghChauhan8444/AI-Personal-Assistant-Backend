package engine

import (
	"path/filepath"
	"testing"
)

func TestASTScanner(t *testing.T) {
	// Root dir points to ../../src from test directory or relative to project root
	absPath, err := filepath.Abs("../../src")
	if err != nil {
		t.Fatalf("failed to resolve path: %v", err)
	}

	reg := NewRegistry()
	scanner := NewASTScanner(absPath, reg)

	res, err := scanner.Scan()
	if err != nil {
		t.Fatalf("scan failed: %v", err)
	}

	if len(res.Packages) == 0 {
		t.Fatalf("expected at least 1 package discovered, got 0")
	}

	t.Logf("Discovered %d packages, %d files, %d types, %d methods",
		res.Summary.PackageCount,
		res.Summary.FileCount,
		res.Summary.TypeCount,
		res.Summary.MethodCount+res.Summary.FunctionCount,
	)

	for _, p := range res.Packages {
		t.Logf("Package %s (%d files, %d methods): %s", p.Name, len(p.Files), len(p.Methods), p.RelPath)
	}

	added := scanner.AutoRegisterDiscoveredModules(reg)
	t.Logf("Auto-registered %d new modules", added)
}

package orchestrator

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/google/uuid"
)

// DefaultSpilloverThresholdBytes defines the 100KB limit beyond which payloads are offloaded to disk.
const DefaultSpilloverThresholdBytes = 100 * 1024

// ArtifactSpillover handles the "Pointers, Not Payloads" architecture invariant.
type ArtifactSpillover struct {
	artifactsDir   string
	thresholdBytes int
}

// NewArtifactSpillover constructs an ArtifactSpillover manager.
func NewArtifactSpillover(artifactsDir string, thresholdBytes int) *ArtifactSpillover {
	if artifactsDir == "" {
		artifactsDir = "workspace/artifacts"
	}
	if thresholdBytes <= 0 {
		thresholdBytes = DefaultSpilloverThresholdBytes
	}
	return &ArtifactSpillover{
		artifactsDir:   artifactsDir,
		thresholdBytes: thresholdBytes,
	}
}

// Process evaluates whether content exceeds the size threshold and spills to disk if necessary.
func (s *ArtifactSpillover) Process(content string) (output string, artifactPath string, spilled bool, err error) {
	if len(content) <= s.thresholdBytes {
		return content, "", false, nil
	}

	if err := os.MkdirAll(s.artifactsDir, 0755); err != nil {
		return content, "", false, fmt.Errorf("failed to create artifacts directory %q: %w", s.artifactsDir, err)
	}

	artifactID := fmt.Sprintf("art_%s.txt", uuid.New().String()[:12])
	filePath := filepath.Join(s.artifactsDir, artifactID)

	if err := os.WriteFile(filePath, []byte(content), 0644); err != nil {
		return content, "", false, fmt.Errorf("failed to write artifact file %q: %w", filePath, err)
	}

	// Create concise 50-line preview
	preview := generatePreview(content, 50)
	spilloverMsg := fmt.Sprintf("%s\n\n[Output truncated (%d bytes). Full payload preserved at: %s]", preview, len(content), filePath)

	return spilloverMsg, filePath, true, nil
}

func generatePreview(content string, maxLines int) string {
	lines := strings.Split(content, "\n")
	if len(lines) <= maxLines {
		return content
	}
	return strings.Join(lines[:maxLines], "\n")
}

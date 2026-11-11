package tools

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// DefaultSpilloverThresholdBytes is the 100KB boundary where outputs spill to disk.
const DefaultSpilloverThresholdBytes = 100 * 1024

// DefaultArtifactsDirectory defines the default folder for spilled payloads.
const DefaultArtifactsDirectory = "workspace/artifacts"

// SpilloverManager enforces the "Pointers, Not Payloads" architecture invariant.
type SpilloverManager struct {
	artifactsDir   string
	thresholdBytes int
}

// NewSpilloverManager constructs a SpilloverManager with explicit directory and threshold.
func NewSpilloverManager(artifactsDir string, thresholdBytes int) *SpilloverManager {
	if artifactsDir == "" {
		artifactsDir = DefaultArtifactsDirectory
	}
	if thresholdBytes <= 0 {
		thresholdBytes = DefaultSpilloverThresholdBytes
	}
	return &SpilloverManager{
		artifactsDir:   artifactsDir,
		thresholdBytes: thresholdBytes,
	}
}

// Process checks content length and writes to disk if exceeding the threshold.
func (sm *SpilloverManager) Process(content string) (string, string, bool, error) {
	if len(content) <= sm.thresholdBytes {
		return content, "", false, nil
	}

	if err := os.MkdirAll(sm.artifactsDir, 0755); err != nil {
		return content, "", false, fmt.Errorf("failed to create artifacts directory: %w", err)
	}

	artifactID := generateArtifactFilename()
	filePath := filepath.Join(sm.artifactsDir, artifactID)

	if err := os.WriteFile(filePath, []byte(content), 0644); err != nil {
		return content, "", false, fmt.Errorf("failed to write spilled artifact: %w", err)
	}

	preview := extractLinePreview(content, 50)
	spilloverNotice := fmt.Sprintf("%s\n\n[Output truncated (%d bytes). Full payload preserved at: %s]", preview, len(content), filePath)

	return spilloverNotice, filePath, true, nil
}

func generateArtifactFilename() string {
	timestamp := time.Now().Format("20060102_150405")
	randomBytes := make([]byte, 4)
	_, _ = rand.Read(randomBytes)
	randomHex := hex.EncodeToString(randomBytes)
	return fmt.Sprintf("art_%s_%s.txt", timestamp, randomHex)
}

func extractLinePreview(content string, maxLines int) string {
	lines := strings.Split(content, "\n")
	if len(lines) <= maxLines {
		return content
	}
	return strings.Join(lines[:maxLines], "\n")
}

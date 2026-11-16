package gateway

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"assistant/src/tools/fs"
)

const maxContextCharacters = 15000

// AttachmentProcessor auto-extracts content from files attached in chat (CLI/Telegram).
type AttachmentProcessor struct {
	docTool   *fs.DocParseTool
	audioTool *fs.AudioTranscribeTool
}

// NewAttachmentProcessor creates a new attachment processor.
func NewAttachmentProcessor() *AttachmentProcessor {
	return &AttachmentProcessor{
		docTool:   fs.NewDocParseTool(),
		audioTool: fs.NewAudioTranscribeTool(),
	}
}

// ProcessAttachment extracts content from a staged file and formats it for prompt injection.
func (p *AttachmentProcessor) ProcessAttachment(ctx context.Context, filePath string) (string, error) {
	if _, err := os.Stat(filePath); err != nil {
		return "", fmt.Errorf("attachment file not found: %w", err)
	}

	ext := strings.ToLower(filepath.Ext(filePath))
	filename := filepath.Base(filePath)

	if isAudioFormat(ext) {
		return p.processAudio(ctx, filePath, filename)
	}

	if isDocumentFormat(ext) || isImageFormat(ext) {
		return p.processDocument(ctx, filePath, filename)
	}

	return fmt.Sprintf("[Attached File: %s (unsupported auto-parse format)]", filename), nil
}

func (p *AttachmentProcessor) processAudio(ctx context.Context, filePath, filename string) (string, error) {
	args := fmt.Sprintf(`{"path": %q, "model": "tiny"}`, filePath)
	res, err := p.audioTool.Execute(ctx, args)
	if err != nil || res.IsError {
		return "", fmt.Errorf("audio transcription failed: %s", res.Stderr)
	}

	transcript := strings.TrimSpace(res.Stdout)
	return fmt.Sprintf("[Voice/Audio Attachment: %s]\nTranscript: %s", filename, transcript), nil
}

func (p *AttachmentProcessor) processDocument(ctx context.Context, filePath, filename string) (string, error) {
	args := fmt.Sprintf(`{"path": %q, "max_pages": 50}`, filePath)
	res, err := p.docTool.Execute(ctx, args)
	if err != nil || res.IsError {
		return "", fmt.Errorf("document parsing failed: %s", res.Stderr)
	}

	content := strings.TrimSpace(res.Stdout)
	if len(content) > maxContextCharacters {
		content = content[:maxContextCharacters] + fmt.Sprintf("\n\n*[Content truncated to %d chars. Total length: %d chars]*", maxContextCharacters, len(res.Stdout))
	}

	return fmt.Sprintf("[Attached Document: %s]\n---\n%s\n---", filename, content), nil
}

func isAudioFormat(ext string) bool {
	switch ext {
	case ".ogg", ".mp3", ".wav", ".m4a", ".flac", ".aac":
		return true
	default:
		return false
	}
}

func isDocumentFormat(ext string) bool {
	switch ext {
	case ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".pptx", ".ppt":
		return true
	default:
		return false
	}
}

func isImageFormat(ext string) bool {
	switch ext {
	case ".png", ".jpg", ".jpeg", ".webp", ".bmp":
		return true
	default:
		return false
	}
}

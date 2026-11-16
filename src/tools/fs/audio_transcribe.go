package fs

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"assistant/src/tools"
)

type AudioTranscribeArgs struct {
	Path  string `json:"path"`
	Model string `json:"model,omitempty"`
}

type AudioTranscribeTool struct {
	pythonBin string
	repoRoot  string
}

func NewAudioTranscribeTool() *AudioTranscribeTool {
	bin, root := resolvePythonBinary()
	return &AudioTranscribeTool{
		pythonBin: bin,
		repoRoot:  root,
	}
}

func (t *AudioTranscribeTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:               "audio_transcribe",
		Category:           "filesystem",
		Description:        "Transcribes audio and voice recordings (MP3, WAV, OGG, M4A) to text using local faster-whisper.",
		ParameterSchema:    `{"type":"object","properties":{"path":{"type":"string","description":"Absolute or relative path to the audio file"},"model":{"type":"string","description":"Whisper model size (tiny, base, small, medium; default: tiny)"}},"required":["path"]}`,
		PromptUsageTip:     "Use audio_transcribe to convert voice memos, audio files, or meeting recordings into text.",
		Risk:               tools.RiskLow,
		RequiredCapability: "fs:read",
	}
}

func (t *AudioTranscribeTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args AudioTranscribeArgs
	if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("invalid arguments for audio_transcribe: %v", err),
		}, nil
	}

	cleanPath := strings.TrimSpace(args.Path)
	if cleanPath == "" {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   "path cannot be empty",
		}, nil
	}

	absPath, err := filepath.Abs(cleanPath)
	if err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("cannot resolve absolute path: %v", err),
		}, nil
	}

	if _, err := os.Stat(absPath); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("audio file not found: %s", absPath),
		}, nil
	}

	model := args.Model
	if model == "" {
		model = "tiny"
	}

	cmdCtx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()

	cmd := exec.CommandContext(cmdCtx, t.pythonBin, "-m", "src.models.audio.transcriber", absPath, "--model", model)
	cmd.Dir = t.repoRoot
	cmd.Env = append(os.Environ(), fmt.Sprintf("PYTHONPATH=%s", t.repoRoot))

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	if err := cmd.Run(); err != nil {
		return &tools.ToolResult{
			IsError:  true,
			ExitCode: 1,
			Stdout:   stdoutBuf.String(),
			Stderr:   fmt.Sprintf("audio_transcribe failed: %v: %s", err, stderrBuf.String()),
		}, nil
	}

	return &tools.ToolResult{
		Stdout:   strings.TrimSpace(stdoutBuf.String()),
		Stderr:   stderrBuf.String(),
		ExitCode: 0,
	}, nil
}

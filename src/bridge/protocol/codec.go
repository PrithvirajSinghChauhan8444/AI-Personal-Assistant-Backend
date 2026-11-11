package protocol

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
)

var (
	// ErrEmptyLine indicates a blank line was received where a frame was expected.
	ErrEmptyLine = errors.New("cannot decode empty line")
	// ErrPayloadTooLarge indicates frame line exceeded acceptable memory bounds.
	ErrPayloadTooLarge = errors.New("frame exceeds maximum allowed size")
)

// MaxLineSizeBytes defines the maximum allowed size of a single NDJSON line (1MB).
const MaxLineSizeBytes = 1024 * 1024

// EncodeMasterFrame encodes a MasterFrame into a single NDJSON line with trailing newline.
func EncodeMasterFrame(frame *MasterFrame) ([]byte, error) {
	if frame == nil {
		return nil, errors.New("cannot encode nil frame")
	}
	if err := frame.Validate(); err != nil {
		return nil, fmt.Errorf("invalid frame: %w", err)
	}

	data, err := json.Marshal(frame)
	if err != nil {
		return nil, fmt.Errorf("failed to encode frame json: %w", err)
	}

	if len(data) > MaxLineSizeBytes {
		return nil, ErrPayloadTooLarge
	}

	data = append(data, '\n')
	return data, nil
}

// DecodeMasterFrame decodes a raw NDJSON line into a MasterFrame.
func DecodeMasterFrame(line []byte) (*MasterFrame, error) {
	trimmed := bytes.TrimSpace(line)
	if len(trimmed) == 0 {
		return nil, ErrEmptyLine
	}
	if len(trimmed) > MaxLineSizeBytes {
		return nil, ErrPayloadTooLarge
	}

	var frame MasterFrame
	if err := json.Unmarshal(trimmed, &frame); err != nil {
		return nil, fmt.Errorf("malformed frame json: %w", err)
	}

	if err := frame.Validate(); err != nil {
		return nil, fmt.Errorf("frame validation failed: %w", err)
	}

	return &frame, nil
}

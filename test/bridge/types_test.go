package bridge_test

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"assistant/src/bridge/protocol"
)

func TestMasterFrameValidation(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name        string
		frame       protocol.MasterFrame
		expectError error
	}{
		{
			name: "valid turn frame",
			frame: protocol.MasterFrame{
				FrameID:     "frm_123",
				SessionID:   "sess_1",
				TurnID:      "turn_1",
				TimestampMs: time.Now().UnixMilli(),
				Type:        protocol.FrameTypeStartTurn,
				Payload:     json.RawMessage(`{"prompt":"hello"}`),
			},
			expectError: nil,
		},
		{
			name: "valid ready handshake without turn_id",
			frame: protocol.MasterFrame{
				FrameID:     "frm_ready",
				SessionID:   "system",
				TimestampMs: time.Now().UnixMilli(),
				Type:        protocol.FrameTypeReady,
				Payload:     json.RawMessage(`{"status":"ready"}`),
			},
			expectError: nil,
		},
		{
			name: "missing frame_id",
			frame: protocol.MasterFrame{
				SessionID: "sess_1",
				TurnID:    "turn_1",
				Type:      protocol.FrameTypeStartTurn,
				Payload:   json.RawMessage(`{}`),
			},
			expectError: protocol.ErrEmptyFrameID,
		},
		{
			name: "missing turn_id on non-ready frame",
			frame: protocol.MasterFrame{
				FrameID:   "frm_123",
				SessionID: "sess_1",
				Type:      protocol.FrameTypeStartTurn,
				Payload:   json.RawMessage(`{}`),
			},
			expectError: protocol.ErrEmptyTurnID,
		},
		{
			name: "empty type",
			frame: protocol.MasterFrame{
				FrameID: "frm_123",
				TurnID:  "turn_1",
				Payload: json.RawMessage(`{}`),
			},
			expectError: protocol.ErrEmptyFrameType,
		},
		{
			name: "nil payload",
			frame: protocol.MasterFrame{
				FrameID: "frm_123",
				TurnID:  "turn_1",
				Type:    protocol.FrameTypeStartTurn,
			},
			expectError: protocol.ErrNilPayload,
		},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			err := tc.frame.Validate()
			if tc.expectError != nil {
				if err != tc.expectError {
					t.Fatalf("expected error %v, got %v", tc.expectError, err)
				}
			} else if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
		})
	}
}

func TestMasterFrameCodecRoundtrip(t *testing.T) {
	t.Parallel()

	original, err := protocol.NewMasterFrame(
		"sess_test",
		"turn_42",
		protocol.FrameTypeStartTurn,
		protocol.StartTurnPayload{
			TargetAgent: "research",
			Prompt:      "Analyze quantum algorithms",
			Messages: []protocol.ChatMessage{
				{Role: "user", Content: "Analyze quantum algorithms"},
			},
		},
	)
	if err != nil {
		t.Fatalf("failed to construct frame: %v", err)
	}

	encoded, err := protocol.EncodeMasterFrame(original)
	if err != nil {
		t.Fatalf("failed to encode frame: %v", err)
	}

	if !strings.HasSuffix(string(encoded), "\n") {
		t.Fatalf("encoded NDJSON frame must terminate with newline")
	}

	decoded, err := protocol.DecodeMasterFrame(encoded)
	if err != nil {
		t.Fatalf("failed to decode frame: %v", err)
	}

	if decoded.FrameID != original.FrameID {
		t.Errorf("frame_id mismatch: got %s, want %s", decoded.FrameID, original.FrameID)
	}
	if decoded.Type != protocol.FrameTypeStartTurn {
		t.Errorf("type mismatch: got %s, want %s", decoded.Type, protocol.FrameTypeStartTurn)
	}

	var payload protocol.StartTurnPayload
	if err := decoded.UnmarshalPayload(&payload); err != nil {
		t.Fatalf("failed to unmarshal payload: %v", err)
	}

	if payload.TargetAgent != "research" {
		t.Errorf("expected target agent research, got %s", payload.TargetAgent)
	}
	if payload.Prompt != "Analyze quantum algorithms" {
		t.Errorf("prompt mismatch: got %s", payload.Prompt)
	}
}

func TestDecodeEmptyLine(t *testing.T) {
	t.Parallel()

	_, err := protocol.DecodeMasterFrame([]byte("   \n"))
	if err != protocol.ErrEmptyLine {
		t.Fatalf("expected ErrEmptyLine, got %v", err)
	}
}

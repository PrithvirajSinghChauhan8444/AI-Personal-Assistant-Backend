package bridge_test

import (
	"bytes"
	"context"
	"io"
	"sync"
	"testing"
	"time"

	"assistant/src/bridge/protocol"
	"assistant/src/bridge/supervisor"
)

type safeBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (s *safeBuffer) Write(p []byte) (n int, err error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.buf.Write(p)
}

func (s *safeBuffer) Bytes() []byte {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.buf.Bytes()
}

func TestMultiplexerSendAndReceive(t *testing.T) {
	t.Parallel()

	r1, w1 := io.Pipe()
	defer r1.Close()
	defer w1.Close()

	outBuf := &safeBuffer{}
	mux := supervisor.NewMultiplexer(r1, outBuf)

	received := make(chan *protocol.MasterFrame, 5)
	mux.On(protocol.FrameTypeToken, func(f *protocol.MasterFrame) {
		received <- f
	})

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	mux.StartReadLoop(ctx, nil)

	// Send a token frame into w1 (simulating incoming data from child)
	frame, err := protocol.NewMasterFrame(
		"sess_test",
		"turn_1",
		protocol.FrameTypeToken,
		protocol.TokenPayload{Delta: "Hello world"},
	)
	if err != nil {
		t.Fatalf("failed to create frame: %v", err)
	}

	encoded, err := protocol.EncodeMasterFrame(frame)
	if err != nil {
		t.Fatalf("failed to encode frame: %v", err)
	}

	go func() {
		_, _ = w1.Write(encoded)
	}()

	select {
	case rec := <-received:
		if rec.Type != protocol.FrameTypeToken {
			t.Errorf("expected token frame type, got %s", rec.Type)
		}
		var token protocol.TokenPayload
		if err := rec.UnmarshalPayload(&token); err != nil {
			t.Fatalf("unmarshal error: %v", err)
		}
		if token.Delta != "Hello world" {
			t.Errorf("expected 'Hello world', got %s", token.Delta)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for multiplexed frame")
	}

	// Test outbound frame writing
	outFrame, err := protocol.NewMasterFrame(
		"sess_test",
		"turn_1",
		protocol.FrameTypeStartTurn,
		protocol.StartTurnPayload{Prompt: "ping"},
	)
	if err != nil {
		t.Fatalf("failed to create outbound frame: %v", err)
	}

	if err := mux.SendFrame(outFrame); err != nil {
		t.Fatalf("failed to send frame via mux: %v", err)
	}

	if len(outBuf.Bytes()) == 0 {
		t.Fatalf("expected written bytes in outbound buffer, got empty")
	}
}

func TestMultiplexerClosedError(t *testing.T) {
	t.Parallel()

	r, w := io.Pipe()
	defer r.Close()
	defer w.Close()

	mux := supervisor.NewMultiplexer(r, w)
	mux.Close()

	frame, _ := protocol.NewMasterFrame("s", "t", protocol.FrameTypeReady, protocol.ReadyPayload{})
	err := mux.SendFrame(frame)
	if err != supervisor.ErrMultiplexerClosed {
		t.Fatalf("expected ErrMultiplexerClosed, got %v", err)
	}
}

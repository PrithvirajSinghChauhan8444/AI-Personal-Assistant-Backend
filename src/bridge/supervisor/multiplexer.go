package supervisor

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"sync"

	"assistant/src/bridge/protocol"
)

var (
	ErrMultiplexerClosed = errors.New("multiplexer is closed")
)

// FrameHandler processes a decoded MasterFrame.
type FrameHandler func(frame *protocol.MasterFrame)

// Multiplexer coordinates thread-safe frame reading and writing over NDJSON streams.
type Multiplexer struct {
	reader   io.Reader
	writer   io.Writer
	writeMu  sync.Mutex
	handlers map[protocol.FrameType][]FrameHandler
	subMu    sync.RWMutex
	closed   bool
	closeMu  sync.Mutex
	doneCh   chan struct{}
}

// NewMultiplexer constructs a Multiplexer over the given reader and writer.
func NewMultiplexer(r io.Reader, w io.Writer) *Multiplexer {
	return &Multiplexer{
		reader:   r,
		writer:   w,
		handlers: make(map[protocol.FrameType][]FrameHandler),
		doneCh:   make(chan struct{}),
	}
}

// On registers a handler callback for a specific frame type.
func (m *Multiplexer) On(frameType protocol.FrameType, handler FrameHandler) {
	m.subMu.Lock()
	defer m.subMu.Unlock()
	m.handlers[frameType] = append(m.handlers[frameType], handler)
}

// SendFrame encodes and writes a MasterFrame to the underlying writer with newline termination.
func (m *Multiplexer) SendFrame(frame *protocol.MasterFrame) error {
	m.closeMu.Lock()
	if m.closed {
		m.closeMu.Unlock()
		return ErrMultiplexerClosed
	}
	m.closeMu.Unlock()

	data, err := protocol.EncodeMasterFrame(frame)
	if err != nil {
		return fmt.Errorf("failed to encode master frame: %w", err)
	}

	m.writeMu.Lock()
	defer m.writeMu.Unlock()

	if _, err := m.writer.Write(data); err != nil {
		return fmt.Errorf("failed to write frame to stream: %w", err)
	}
	return nil
}

// StartReadLoop begins scanning and decoding NDJSON frames until EOF or error.
func (m *Multiplexer) StartReadLoop(ctx context.Context, onDisconnect func(err error)) {
	go func() {
		defer close(m.doneCh)
		scanner := bufio.NewScanner(m.reader)
		buf := make([]byte, 64*1024)
		scanner.Buffer(buf, protocol.MaxLineSizeBytes)

		for scanner.Scan() {
			select {
			case <-ctx.Done():
				return
			default:
			}

			line := scanner.Bytes()
			frame, err := protocol.DecodeMasterFrame(line)
			if err != nil {
				// Malformed line or empty, skip safely
				continue
			}

			m.dispatch(frame)
		}

		scanErr := scanner.Err()
		m.Close()
		if onDisconnect != nil {
			onDisconnect(scanErr)
		}
	}()
}

// Done returns a channel that is closed when reading terminates.
func (m *Multiplexer) Done() <-chan struct{} {
	return m.doneCh
}

// Close marks the multiplexer as closed.
func (m *Multiplexer) Close() {
	m.closeMu.Lock()
	defer m.closeMu.Unlock()
	m.closed = true
}

func (m *Multiplexer) dispatch(frame *protocol.MasterFrame) {
	m.subMu.RLock()
	defer m.subMu.RUnlock()

	handlers := m.handlers[frame.Type]
	for _, h := range handlers {
		h(frame)
	}
}

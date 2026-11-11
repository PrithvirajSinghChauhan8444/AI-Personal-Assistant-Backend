package supervisor

import (
	"sync"

	"assistant/src/bridge/protocol"
)

// TurnHandle manages the streaming lifecycle of a single active turn.
type TurnHandle struct {
	sessionID    string
	turnID       string
	tokenCh      chan string
	thoughtCh    chan string
	completeCh   chan *protocol.TurnCompletePayload
	errCh        chan error
	closeOnce    sync.Once
	closed       bool
	closedMu     sync.RWMutex
}

// NewTurnHandle initializes an active turn stream handle with buffered channels.
func NewTurnHandle(sessionID, turnID string) *TurnHandle {
	return &TurnHandle{
		sessionID:  sessionID,
		turnID:     turnID,
		tokenCh:    make(chan string, 128),
		thoughtCh:  make(chan string, 64),
		completeCh: make(chan *protocol.TurnCompletePayload, 1),
		errCh:      make(chan error, 1),
	}
}

// SessionID returns the identifier of the conversation session.
func (h *TurnHandle) SessionID() string {
	return h.sessionID
}

// TurnID returns the unique identifier of the turn.
func (h *TurnHandle) TurnID() string {
	return h.turnID
}

// Tokens returns a read-only channel of streamed text deltas.
func (h *TurnHandle) Tokens() <-chan string {
	return h.tokenCh
}

// Thoughts returns a read-only channel of internal agent thoughts.
func (h *TurnHandle) Thoughts() <-chan string {
	return h.thoughtCh
}

// Complete returns a read-only channel delivering the terminal turn payload.
func (h *TurnHandle) Complete() <-chan *protocol.TurnCompletePayload {
	return h.completeCh
}

// Errors returns a read-only channel delivering terminal errors.
func (h *TurnHandle) Errors() <-chan error {
	return h.errCh
}

// PushToken sends a text delta non-blockingly.
func (h *TurnHandle) PushToken(token string) {
	h.closedMu.RLock()
	defer h.closedMu.RUnlock()
	if h.closed {
		return
	}
	select {
	case h.tokenCh <- token:
	default:
	}
}

// PushThought sends an agent thought non-blockingly.
func (h *TurnHandle) PushThought(thought string) {
	h.closedMu.RLock()
	defer h.closedMu.RUnlock()
	if h.closed {
		return
	}
	select {
	case h.thoughtCh <- thought:
	default:
	}
}

// Finish emits the completion payload and closes stream channels.
func (h *TurnHandle) Finish(complete *protocol.TurnCompletePayload) {
	h.closeOnce.Do(func() {
		h.closedMu.Lock()
		h.closed = true
		h.closedMu.Unlock()

		if complete != nil {
			h.completeCh <- complete
		}
		close(h.completeCh)
		close(h.tokenCh)
		close(h.thoughtCh)
		close(h.errCh)
	})
}

// Fail emits an error and closes stream channels.
func (h *TurnHandle) Fail(err error) {
	h.closeOnce.Do(func() {
		h.closedMu.Lock()
		h.closed = true
		h.closedMu.Unlock()

		if err != nil {
			h.errCh <- err
		}
		close(h.errCh)
		close(h.tokenCh)
		close(h.thoughtCh)
		close(h.completeCh)
	})
}

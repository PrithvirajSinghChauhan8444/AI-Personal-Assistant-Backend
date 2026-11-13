package web

import (
	"bufio"
	"context"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"

	"assistant/src/gateway"
	"github.com/google/uuid"
)

const (
	wsGUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
)

// WebAdapter exposes the Modular Execution Observer API over HTTP, WebSockets, and Server-Sent Events.
type WebAdapter struct {
	gw          *gateway.Gateway
	mux         *http.ServeMux
	server      *http.Server
	clientsMu   sync.RWMutex
	sseClients  map[string]map[chan gateway.OutboundEvent]struct{} // sessionID -> set of channels
	wsClients   map[string]map[net.Conn]struct{}                   // sessionID -> set of conns
	allSSE      map[chan gateway.OutboundEvent]struct{}            // global listeners
	allWS       map[net.Conn]struct{}                              // global listeners
	maxBufSize  int
}

// TurnSubmissionPayload represents JSON body for POST /api/turn.
type TurnSubmissionPayload struct {
	SessionID           string              `json:"session_id"`
	UserID              string              `json:"user_id"`
	Prompt              string              `json:"prompt"`
	TargetAgent         string              `json:"target_agent,omitempty"`
	Trigger             gateway.TriggerType `json:"trigger,omitempty"`
	AllowedCapabilities []string            `json:"allowed_capabilities,omitempty"`
}

// HITLSubmissionPayload represents JSON body for POST /api/hitl.
type HITLSubmissionPayload struct {
	RequestID    string `json:"request_id"`
	SessionID    string `json:"session_id"`
	Approved     bool   `json:"approved"`
	UserFeedback string `json:"user_feedback,omitempty"`
}

// NewWebAdapter constructs a WebAdapter backed by the gateway.
func NewWebAdapter(gw *gateway.Gateway) *WebAdapter {
	adapter := &WebAdapter{
		gw:         gw,
		mux:        http.NewServeMux(),
		sseClients: make(map[string]map[chan gateway.OutboundEvent]struct{}),
		wsClients:  make(map[string]map[net.Conn]struct{}),
		allSSE:     make(map[chan gateway.OutboundEvent]struct{}),
		allWS:      make(map[net.Conn]struct{}),
		maxBufSize: 64,
	}

	adapter.registerRoutes()
	_ = gw.RegisterObserver("web_adapter", adapter)

	return adapter
}

// Handler returns the HTTP handler for integration into existing routers or test servers.
func (a *WebAdapter) Handler() http.Handler {
	return a.mux
}

// OnEvent implements gateway.ExecutionObserver to broadcast live execution events to web clients.
func (a *WebAdapter) OnEvent(ctx context.Context, ev gateway.OutboundEvent) {
	a.broadcastSSE(ev)
	a.broadcastWS(ev)
}

func (a *WebAdapter) registerRoutes() {
	a.mux.HandleFunc("/api/turn", a.handleTurn)
	a.mux.HandleFunc("/api/snapshot", a.handleSnapshot)
	a.mux.HandleFunc("/api/logs", a.handleLogs)
	a.mux.HandleFunc("/api/hitl", a.handleHITL)
	a.mux.HandleFunc("/api/stream", a.handleSSE)
	a.mux.HandleFunc("/ws", a.handleWS)
}

// POST /api/turn - Submit a new turn execution
func (a *WebAdapter) handleTurn(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var payload TurnSubmissionPayload
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, fmt.Sprintf("invalid JSON body: %v", err), http.StatusBadRequest)
		return
	}

	if strings.TrimSpace(payload.Prompt) == "" {
		http.Error(w, "prompt cannot be empty", http.StatusBadRequest)
		return
	}

	sessionID := payload.SessionID
	if sessionID == "" {
		sessionID = uuid.NewString()
	}

	inbound := gateway.InboundTurnRequest{
		SessionID:           sessionID,
		UserID:              payload.UserID,
		Channel:             gateway.ClientTypeWeb,
		Trigger:             payload.Trigger,
		TargetAgent:         payload.TargetAgent,
		AllowedCapabilities: payload.AllowedCapabilities,
		Prompt:              payload.Prompt,
	}

	eventCh, normalizedReq, err := a.gw.SubmitTurn(r.Context(), inbound)
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to submit turn: %v", err), http.StatusInternalServerError)
		return
	}

	// Drain eventCh in background so execution continues regardless of HTTP response lifecycle
	go func() {
		for range eventCh {
			// Hub already processed and dispatched to OnEvent
		}
	}()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status":     "accepted",
		"session_id": normalizedReq.SessionID,
		"trace_id":   normalizedReq.TraceID,
	})
}

// GET /api/snapshot - Query state snapshot ("What is happening right now?")
func (a *WebAdapter) handleSnapshot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	sessionID := r.URL.Query().Get("session_id")
	w.Header().Set("Content-Type", "application/json")

	if sessionID != "" {
		snap, err := a.gw.GetSnapshot(sessionID)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}
		_ = json.NewEncoder(w).Encode(snap)
		return
	}

	snapshots := a.gw.GetActiveSnapshots()
	_ = json.NewEncoder(w).Encode(snapshots)
}

// GET /api/logs - Historical turn log and diagnostic trace retrieval
func (a *WebAdapter) handleLogs(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	turnID := r.URL.Query().Get("turn_id")
	if turnID == "" {
		http.Error(w, "turn_id query parameter is required", http.StatusBadRequest)
		return
	}

	logs, err := a.gw.GetTurnLogs(turnID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(logs)
}

// POST /api/hitl - Human-in-the-loop approval or rejection response
func (a *WebAdapter) handleHITL(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var payload HITLSubmissionPayload
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, fmt.Sprintf("invalid JSON body: %v", err), http.StatusBadRequest)
		return
	}

	if payload.RequestID == "" {
		http.Error(w, "request_id is required", http.StatusBadRequest)
		return
	}

	resp := gateway.HITLResponse{
		RequestID:    payload.RequestID,
		SessionID:    payload.SessionID,
		Approved:     payload.Approved,
		UserFeedback: payload.UserFeedback,
		RespondedAt:  time.Now().UTC(),
	}

	if err := a.gw.RespondHITL(r.Context(), resp); err != nil {
		http.Error(w, fmt.Sprintf("failed to submit HITL response: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status": "success",
	})
}

// GET /api/stream - Server-Sent Events (SSE) streaming endpoint
func (a *WebAdapter) handleSSE(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
		return
	}

	sessionID := r.URL.Query().Get("session_id")

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	ch := make(chan gateway.OutboundEvent, a.maxBufSize)
	a.registerSSEClient(sessionID, ch)
	defer a.unregisterSSEClient(sessionID, ch)

	// Send initial snapshot as greeting if session_id provided
	if sessionID != "" {
		if snap, err := a.gw.GetSnapshot(sessionID); err == nil {
			data, _ := json.Marshal(snap)
			_, _ = fmt.Fprintf(w, "event: snapshot\ndata: %s\n\n", string(data))
			flusher.Flush()
		}
	}

	notify := r.Context().Done()
	for {
		select {
		case <-notify:
			return
		case ev := <-ch:
			data, err := json.Marshal(ev)
			if err != nil {
				continue
			}
			_, _ = fmt.Fprintf(w, "event: %s\ndata: %s\n\n", ev.Type, string(data))
			flusher.Flush()
		}
	}
}

// GET /ws - WebSocket streaming endpoint (RFC 6455)
func (a *WebAdapter) handleWS(w http.ResponseWriter, r *http.Request) {
	if !strings.EqualFold(r.Header.Get("Upgrade"), "websocket") {
		http.Error(w, "Expected websocket upgrade", http.StatusBadRequest)
		return
	}

	key := r.Header.Get("Sec-WebSocket-Key")
	if key == "" {
		http.Error(w, "Missing Sec-WebSocket-Key", http.StatusBadRequest)
		return
	}

	hj, ok := w.(http.Hijacker)
	if !ok {
		http.Error(w, "Websocket hijacking not supported", http.StatusInternalServerError)
		return
	}

	conn, bufrw, err := hj.Hijack()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer conn.Close()

	// Compute accept hash
	h := sha1.New()
	h.Write([]byte(key + wsGUID))
	accept := base64.StdEncoding.EncodeToString(h.Sum(nil))

	// Send handshake response
	handshake := fmt.Sprintf("HTTP/1.1 101 Switching Protocols\r\n"+
		"Upgrade: websocket\r\n"+
		"Connection: Upgrade\r\n"+
		"Sec-WebSocket-Accept: %s\r\n\r\n", accept)
	if _, err := bufrw.WriteString(handshake); err != nil {
		return
	}
	_ = bufrw.Flush()

	sessionID := r.URL.Query().Get("session_id")
	a.registerWSClient(sessionID, conn)
	defer a.unregisterWSClient(sessionID, conn)

	// Send initial snapshot if available
	if sessionID != "" {
		if snap, err := a.gw.GetSnapshot(sessionID); err == nil {
			if data, err := json.Marshal(snap); err == nil {
				_ = writeWSFrame(conn, 0x1, data)
			}
		}
	}

	// Listen for incoming frames from the client (e.g. prompt or HITL responses)
	a.readWSFrames(r.Context(), conn, bufrw.Reader, sessionID)
}

func (a *WebAdapter) readWSFrames(ctx context.Context, conn net.Conn, r *bufio.Reader, defaultSessionID string) {
	for {
		header := make([]byte, 2)
		if _, err := io.ReadFull(r, header); err != nil {
			return
		}

		fin := header[0]&0x80 != 0
		opcode := header[0] & 0x0F
		masked := header[1]&0x80 != 0
		payloadLen := uint64(header[1] & 0x7F)

		if opcode == 0x8 { // Connection close
			return
		}

		if payloadLen == 126 {
			ext := make([]byte, 2)
			if _, err := io.ReadFull(r, ext); err != nil {
				return
			}
			payloadLen = uint64(binary.BigEndian.Uint16(ext))
		} else if payloadLen == 127 {
			ext := make([]byte, 8)
			if _, err := io.ReadFull(r, ext); err != nil {
				return
			}
			payloadLen = binary.BigEndian.Uint64(ext)
		}

		maskKey := make([]byte, 4)
		if masked {
			if _, err := io.ReadFull(r, maskKey); err != nil {
				return
			}
		}

		payload := make([]byte, payloadLen)
		if _, err := io.ReadFull(r, payload); err != nil {
			return
		}

		if masked {
			for i := uint64(0); i < payloadLen; i++ {
				payload[i] ^= maskKey[i%4]
			}
		}

		if opcode == 0x9 { // Ping -> send Pong
			_ = writeWSFrame(conn, 0xA, payload)
			continue
		}

		if opcode == 0x1 && fin { // Text frame
			a.handleIncomingWSMessage(ctx, payload, defaultSessionID)
		}
	}
}

func (a *WebAdapter) handleIncomingWSMessage(ctx context.Context, payload []byte, defaultSessionID string) {
	var raw map[string]interface{}
	if err := json.Unmarshal(payload, &raw); err != nil {
		return
	}

	msgType, _ := raw["type"].(string)
	switch strings.ToLower(msgType) {
	case "turn", "prompt":
		prompt, _ := raw["prompt"].(string)
		sessID, _ := raw["session_id"].(string)
		if sessID == "" {
			sessID = defaultSessionID
		}
		if sessID == "" {
			sessID = uuid.NewString()
		}
		if prompt != "" {
			req := gateway.InboundTurnRequest{
				SessionID: sessID,
				Channel:   gateway.ClientTypeWeb,
				Prompt:    prompt,
			}
			_, _, _ = a.gw.SubmitTurn(ctx, req)
		}

	case "hitl", "approval":
		reqID, _ := raw["request_id"].(string)
		approved, _ := raw["approved"].(bool)
		feedback, _ := raw["feedback"].(string)
		if reqID != "" {
			_ = a.gw.RespondHITL(ctx, gateway.HITLResponse{
				RequestID:    reqID,
				Approved:     approved,
				UserFeedback: feedback,
				RespondedAt:  time.Now().UTC(),
			})
		}
	}
}

func (a *WebAdapter) registerSSEClient(sessionID string, ch chan gateway.OutboundEvent) {
	a.clientsMu.Lock()
	defer a.clientsMu.Unlock()

	if sessionID != "" {
		if _, exists := a.sseClients[sessionID]; !exists {
			a.sseClients[sessionID] = make(map[chan gateway.OutboundEvent]struct{})
		}
		a.sseClients[sessionID][ch] = struct{}{}
	} else {
		a.allSSE[ch] = struct{}{}
	}
}

func (a *WebAdapter) unregisterSSEClient(sessionID string, ch chan gateway.OutboundEvent) {
	a.clientsMu.Lock()
	defer a.clientsMu.Unlock()

	if sessionID != "" {
		if set, exists := a.sseClients[sessionID]; exists {
			delete(set, ch)
			if len(set) == 0 {
				delete(a.sseClients, sessionID)
			}
		}
	}
	delete(a.allSSE, ch)
}

func (a *WebAdapter) registerWSClient(sessionID string, conn net.Conn) {
	a.clientsMu.Lock()
	defer a.clientsMu.Unlock()

	if sessionID != "" {
		if _, exists := a.wsClients[sessionID]; !exists {
			a.wsClients[sessionID] = make(map[net.Conn]struct{})
		}
		a.wsClients[sessionID][conn] = struct{}{}
	} else {
		a.allWS[conn] = struct{}{}
	}
}

func (a *WebAdapter) unregisterWSClient(sessionID string, conn net.Conn) {
	a.clientsMu.Lock()
	defer a.clientsMu.Unlock()

	if sessionID != "" {
		if set, exists := a.wsClients[sessionID]; exists {
			delete(set, conn)
			if len(set) == 0 {
				delete(a.wsClients, sessionID)
			}
		}
	}
	delete(a.allWS, conn)
}

func (a *WebAdapter) broadcastSSE(ev gateway.OutboundEvent) {
	a.clientsMu.RLock()
	var targets []chan gateway.OutboundEvent

	if ev.SessionID != "" {
		if set, exists := a.sseClients[ev.SessionID]; exists {
			for ch := range set {
				targets = append(targets, ch)
			}
		}
	}
	for ch := range a.allSSE {
		targets = append(targets, ch)
	}
	a.clientsMu.RUnlock()

	for _, ch := range targets {
		select {
		case ch <- ev:
		default:
			// Non-blocking drop if client is saturated
		}
	}
}

func (a *WebAdapter) broadcastWS(ev gateway.OutboundEvent) {
	data, err := json.Marshal(ev)
	if err != nil {
		return
	}

	a.clientsMu.RLock()
	var targets []net.Conn

	if ev.SessionID != "" {
		if set, exists := a.wsClients[ev.SessionID]; exists {
			for conn := range set {
				targets = append(targets, conn)
			}
		}
	}
	for conn := range a.allWS {
		targets = append(targets, conn)
	}
	a.clientsMu.RUnlock()

	for _, conn := range targets {
		_ = writeWSFrame(conn, 0x1, data)
	}
}

// writeWSFrame writes an unmasked server-to-client WebSocket frame.
func writeWSFrame(w io.Writer, opcode byte, payload []byte) error {
	length := len(payload)
	var header []byte

	if length <= 125 {
		header = []byte{0x80 | opcode, byte(length)}
	} else if length <= 65535 {
		header = make([]byte, 4)
		header[0] = 0x80 | opcode
		header[1] = 126
		binary.BigEndian.PutUint16(header[2:4], uint16(length))
	} else {
		header = make([]byte, 10)
		header[0] = 0x80 | opcode
		header[1] = 127
		binary.BigEndian.PutUint64(header[2:10], uint64(length))
	}

	if _, err := w.Write(header); err != nil {
		return err
	}
	_, err := w.Write(payload)
	return err
}

// Start launches a listening HTTP server on the specified network address.
func (a *WebAdapter) Start(addr string) error {
	a.server = &http.Server{
		Addr:    addr,
		Handler: a.mux,
	}
	return a.server.ListenAndServe()
}

// Shutdown gracefully stops the web server.
func (a *WebAdapter) Shutdown(ctx context.Context) error {
	if a.server == nil {
		return errors.New("server is not running")
	}
	return a.server.Shutdown(ctx)
}

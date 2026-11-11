package engine

import (
	"context"
	"fmt"
	"runtime"
	"sync"
	"time"

	"github.com/google/uuid"
)

// APIRequestLog captures telemetry for every HTTP API interaction with the workbench.
type APIRequestLog struct {
	ID                string    `json:"id"`
	Timestamp         time.Time `json:"timestamp"`
	Method            string    `json:"method"`
	Path              string    `json:"path"`
	Status            int       `json:"status"`
	DurationUs        int64     `json:"duration_us"`
	DurationFormatted string    `json:"duration_formatted"`
	ClientIP          string    `json:"client_ip"`
	BytesReceived     int64     `json:"bytes_received"`
	BytesSent         int64     `json:"bytes_sent"`
	TraceID           string    `json:"trace_id"`
	RequestBody       string    `json:"request_body,omitempty"`
	ResponseBody      string    `json:"response_body,omitempty"`
}

// GoLogEntry captures structured logs emitted by Go backend services and modules.
type GoLogEntry struct {
	Timestamp   time.Time      `json:"timestamp"`
	Level       string         `json:"level"` // DEBUG, INFO, WARN, ERROR
	Source      string         `json:"source"`
	ExecutionID string         `json:"execution_id,omitempty"`
	TraceID     string         `json:"trace_id,omitempty"`
	Message     string         `json:"message"`
	Fields      map[string]any `json:"fields,omitempty"`
}

// RuntimeTelemetry measures memory and concurrency health across a request.
type RuntimeTelemetry struct {
	TraceID            string `json:"trace_id"`
	SpanID             string `json:"span_id"`
	GoroutinesStart    int    `json:"goroutines_start"`
	GoroutinesEnd      int    `json:"goroutines_end"`
	GoroutineDelta     int    `json:"goroutine_delta"`
	MemAllocStartBytes uint64 `json:"mem_alloc_start_bytes"`
	MemAllocEndBytes   uint64 `json:"mem_alloc_end_bytes"`
	MemDeltaBytes      int64  `json:"mem_delta_bytes"`
	NumGC              uint32 `json:"num_gc"`
}

// TelemetryHub manages in-memory circular buffers of API logs and Go runtime logs.
type TelemetryHub struct {
	mu           sync.RWMutex
	apiRequests  []APIRequestLog
	goLogs       []GoLogEntry
	maxAPILogs   int
	maxGoLogs    int
	subscribers  map[chan any]struct{}
}

// GlobalTelemetry is the shared singleton telemetry collector.
var GlobalTelemetry = NewTelemetryHub(200, 500)

// NewTelemetryHub initializes a new telemetry buffer.
func NewTelemetryHub(maxAPILogs, maxGoLogs int) *TelemetryHub {
	return &TelemetryHub{
		apiRequests: make([]APIRequestLog, 0, maxAPILogs),
		goLogs:      make([]GoLogEntry, 0, maxGoLogs),
		maxAPILogs:  maxAPILogs,
		maxGoLogs:   maxGoLogs,
		subscribers: make(map[chan any]struct{}),
	}
}

// RecordAPIRequest appends an HTTP request record to the telemetry buffer.
func (h *TelemetryHub) RecordAPIRequest(req APIRequestLog) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if len(h.apiRequests) >= h.maxAPILogs {
		h.apiRequests = h.apiRequests[1:]
	}
	h.apiRequests = append(h.apiRequests, req)

	// Broadcast to active subscribers
	h.broadcast(map[string]any{
		"type": "API_LOG",
		"data": req,
	})
}

// RecordGoLog appends a structured Go log entry and prints to stdout with timestamp.
func (h *TelemetryHub) RecordGoLog(entry GoLogEntry) {
	h.mu.Lock()
	if entry.Timestamp.IsZero() {
		entry.Timestamp = time.Now().UTC()
	}

	if len(h.goLogs) >= h.maxGoLogs {
		h.goLogs = h.goLogs[1:]
	}
	h.goLogs = append(h.goLogs, entry)

	h.broadcast(map[string]any{
		"type": "GO_LOG",
		"data": entry,
	})
	h.mu.Unlock()

	// Console mirror for developer terminal
	fmt.Printf("[%s] [%-5s] [%s] %s\n",
		entry.Timestamp.Format("15:04:05.000"),
		entry.Level,
		entry.Source,
		entry.Message,
	)
}

func (h *TelemetryHub) broadcast(msg any) {
	for ch := range h.subscribers {
		select {
		case ch <- msg:
		default:
		}
	}
}

// Subscribe opens a live telemetry feed channel.
func (h *TelemetryHub) Subscribe() (chan any, func()) {
	h.mu.Lock()
	defer h.mu.Unlock()

	ch := make(chan any, 64)
	h.subscribers[ch] = struct{}{}

	unsubscribe := func() {
		h.mu.Lock()
		defer h.mu.Unlock()
		delete(h.subscribers, ch)
		close(ch)
	}

	return ch, unsubscribe
}

// GetRecentAPIRequests returns recent HTTP API telemetry entries.
func (h *TelemetryHub) GetRecentAPIRequests(limit int) []APIRequestLog {
	h.mu.RLock()
	defer h.mu.RUnlock()

	n := len(h.apiRequests)
	if limit <= 0 || limit > n {
		limit = n
	}

	result := make([]APIRequestLog, limit)
	copy(result, h.apiRequests[n-limit:])
	return result
}

// GetRecentGoLogs returns recent Go system log entries.
func (h *TelemetryHub) GetRecentGoLogs(limit int) []GoLogEntry {
	h.mu.RLock()
	defer h.mu.RUnlock()

	n := len(h.goLogs)
	if limit <= 0 || limit > n {
		limit = n
	}

	result := make([]GoLogEntry, limit)
	copy(result, h.goLogs[n-limit:])
	return result
}

// SnapshotRuntimeTelemetry captures current memory and goroutine stats.
func SnapshotRuntimeTelemetry(traceID, spanID string) (*RuntimeTelemetry, func() *RuntimeTelemetry) {
	if traceID == "" {
		traceID = uuid.New().String()
	}
	if spanID == "" {
		spanID = uuid.New().String()[:16]
	}

	var mStart runtime.MemStats
	runtime.ReadMemStats(&mStart)
	goroutinesStart := runtime.NumGoroutine()

	startTelemetry := &RuntimeTelemetry{
		TraceID:            traceID,
		SpanID:             spanID,
		GoroutinesStart:    goroutinesStart,
		MemAllocStartBytes: mStart.Alloc,
		NumGC:              mStart.NumGC,
	}

	finish := func() *RuntimeTelemetry {
		var mEnd runtime.MemStats
		runtime.ReadMemStats(&mEnd)
		goroutinesEnd := runtime.NumGoroutine()

		final := *startTelemetry
		final.GoroutinesEnd = goroutinesEnd
		final.GoroutineDelta = goroutinesEnd - goroutinesStart
		final.MemAllocEndBytes = mEnd.Alloc
		final.MemDeltaBytes = int64(mEnd.Alloc) - int64(mStart.Alloc)
		final.NumGC = mEnd.NumGC - mStart.NumGC

		return &final
	}

	return startTelemetry, finish
}

// ContextWithTrace attaches trace telemetry context.
type traceContextKey struct{}

func ContextWithTrace(ctx context.Context, traceID, spanID string) context.Context {
	return context.WithValue(ctx, traceContextKey{}, map[string]string{
		"trace_id": traceID,
		"span_id":  spanID,
	})
}

func TraceFromContext(ctx context.Context) (traceID, spanID string) {
	val := ctx.Value(traceContextKey{})
	if m, ok := val.(map[string]string); ok {
		return m["trace_id"], m["span_id"]
	}
	return "", ""
}

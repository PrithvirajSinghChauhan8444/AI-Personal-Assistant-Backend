package workbench

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"syscall"
	"time"

	"assistant/src/gateway"
	"assistant/workbench/engine"
	"assistant/workbench/modules"
	"assistant/workbench/web"

	"github.com/google/uuid"
)

type executeRequest struct {
	ModuleID       string          `json:"module_id"`
	Input          json.RawMessage `json:"input"`
	TimeoutSeconds int             `json:"timeout_seconds"`
}

type abortRequest struct {
	ExecutionID string `json:"execution_id"`
}

type statusRecordingResponseWriter struct {
	http.ResponseWriter
	statusCode   int
	bytesWritten int64
}

func (w *statusRecordingResponseWriter) WriteHeader(code int) {
	w.statusCode = code
	w.ResponseWriter.WriteHeader(code)
}

func (w *statusRecordingResponseWriter) Write(b []byte) (int, error) {
	if w.statusCode == 0 {
		w.statusCode = http.StatusOK
	}
	n, err := w.ResponseWriter.Write(b)
	w.bytesWritten += int64(n)
	return n, err
}

func (w *statusRecordingResponseWriter) Flush() {
	if f, ok := w.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

// Start launches the Module Workbench HTTP Server and blocks until SIGINT/SIGTERM.
func Start(port int, historyDir string) error {
	recorder, err := engine.NewRecorder(historyDir)
	if err != nil {
		return fmt.Errorf("error initializing recorder: %w", err)
	}

	registry := engine.NewRegistry()
	supervisor := engine.NewSupervisor(registry, recorder)

	// Register All Core Modules & Pipelines
	modules.RegisterLayer1Gateway(registry, supervisor)
	modules.RegisterLayer2Orchestrator(registry, supervisor)
	modules.RegisterLayer3Tools(registry)
	modules.RegisterLayer4Bridge(registry)
	modules.RegisterLayer6Agent(registry)
	modules.RegisterSafetyGatekeeper(registry)
	modules.RegisterSessionStore(registry)
	modules.RegisterE2EPipeline(registry, supervisor)

	// Initialize AST Codebase Scanner & Hot File Watcher
	srcRoot := engine.FindSourceRoot()
	scanner := engine.NewASTScanner(srcRoot, registry)
	if _, err := scanner.Scan(); err == nil {
		scanner.AutoRegisterDiscoveredModules(registry)
	}
	// Start real-time hot file watcher (detects new/modified Go & Python files continuously)
	scanner.StartHotWatcher(1500 * time.Millisecond)

	mux := http.NewServeMux()

	// API: List Modules
	mux.HandleFunc("GET /api/modules", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		mods := registry.List()
		_ = json.NewEncoder(w).Encode(mods)
	})

	// API: Execute Module with Live SSE Streaming
	mux.HandleFunc("POST /api/execute", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Trace-ID")

		var req executeRequest
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "failed to read body", http.StatusBadRequest)
			return
		}
		if err := json.Unmarshal(body, &req); err != nil {
			http.Error(w, "invalid JSON payload", http.StatusBadRequest)
			return
		}

		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "streaming unsupported", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")

		timeout := 60 * time.Second
		if req.TimeoutSeconds > 0 {
			timeout = time.Duration(req.TimeoutSeconds) * time.Second
		}
		execCtx, cancel := context.WithTimeout(r.Context(), timeout)
		defer cancel()

		streamChan := make(chan engine.StreamEvent, 64)

		type runResult struct {
			record *engine.ExecutionRecord
			err    error
		}
		resChan := make(chan runResult, 1)

		go func() {
			rec, runErr := supervisor.Execute(execCtx, req.ModuleID, req.Input, streamChan)
			resChan <- runResult{record: rec, err: runErr}
			close(streamChan)
		}()

		// Forward streaming events to client via SSE
		for ev := range streamChan {
			data, _ := json.Marshal(ev)
			fmt.Fprintf(w, "event: event\ndata: %s\n\n", data)
			flusher.Flush()
		}

		res := <-resChan
		if res.record != nil {
			recData, _ := json.Marshal(res.record)
			fmt.Fprintf(w, "event: complete\ndata: %s\n\n", recData)
			flusher.Flush()
		}
	})

	// API: Abort In-Flight Execution
	mux.HandleFunc("POST /api/abort", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

		var req abortRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid JSON", http.StatusBadRequest)
			return
		}

		aborted := supervisor.Abort(req.ExecutionID)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"execution_id": req.ExecutionID,
			"aborted":      aborted,
		})
	})

	// API: Submit Human In The Loop (HITL) Decision
	mux.HandleFunc("POST /api/hitl", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

		var resp gateway.HITLResponse
		if err := json.NewDecoder(r.Body).Decode(&resp); err != nil {
			http.Error(w, "invalid JSON", http.StatusBadRequest)
			return
		}
		if resp.RespondedAt.IsZero() {
			resp.RespondedAt = time.Now().UTC()
		}

		delivered := supervisor.SubmitHITL(resp)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"delivered":  delivered,
			"request_id": resp.RequestID,
		})
	})

	// API: List Flight History
	mux.HandleFunc("GET /api/history", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")

		records, err := recorder.List(50)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		_ = json.NewEncoder(w).Encode(records)
	})

	// API: Get Flight History by ID
	mux.HandleFunc("GET /api/history/{id}", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")

		id := r.PathValue("id")
		record, err := recorder.GetByID(id)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}
		_ = json.NewEncoder(w).Encode(record)
	})

	// API: Get System & Telemetry Snapshot
	mux.HandleFunc("GET /api/telemetry", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")

		var m runtime.MemStats
		runtime.ReadMemStats(&m)

		_ = json.NewEncoder(w).Encode(map[string]any{
			"api_requests": engine.GlobalTelemetry.GetRecentAPIRequests(50),
			"go_logs":      engine.GlobalTelemetry.GetRecentGoLogs(100),
			"system": map[string]any{
				"goroutines":    runtime.NumGoroutine(),
				"mem_alloc_mb":  float64(m.Alloc) / (1024 * 1024),
				"mem_total_mb":  float64(m.TotalAlloc) / (1024 * 1024),
				"mem_sys_mb":    float64(m.Sys) / (1024 * 1024),
				"num_gc":        m.NumGC,
				"num_cpu":       runtime.NumCPU(),
			},
		})
	})

	// API: Real-time Telemetry & Log Stream (SSE)
	mux.HandleFunc("GET /api/telemetry/stream", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "streaming unsupported", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")

		ch, unsubscribe := engine.GlobalTelemetry.Subscribe()
		defer unsubscribe()

		notify := r.Context().Done()
		for {
			select {
			case <-notify:
				return
			case item, open := <-ch:
				if !open {
					return
				}
				data, _ := json.Marshal(item)
				fmt.Fprintf(w, "event: telemetry\ndata: %s\n\n", data)
				flusher.Flush()
			}
		}
	})

	// API: Get AST Scan Summary
	mux.HandleFunc("GET /api/scanner/summary", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		res, err := scanner.GetLastResult()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		_ = json.NewEncoder(w).Encode(res.Summary)
	})

	// API: Get AST Details (All packages, types, methods)
	mux.HandleFunc("GET /api/scanner/details", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		res, err := scanner.GetLastResult()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		_ = json.NewEncoder(w).Encode(res)
	})

	// API: Force Rescan Codebase
	mux.HandleFunc("POST /api/scanner/rescan", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		res, err := scanner.Scan()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		added := scanner.AutoRegisterDiscoveredModules(registry)
		engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
			Timestamp:   time.Now(),
			Level:       "INFO",
			Source:      "ASTScanner",
			ExecutionID: "",
			TraceID:     "",
			Message:     fmt.Sprintf("AST scan completed: %d packages, %d types, %d methods. Auto-registered %d modules.", res.Summary.PackageCount, res.Summary.TypeCount, res.Summary.MethodCount+res.Summary.FunctionCount, added),
		})
		_ = json.NewEncoder(w).Encode(res)
	})

	// Static Web Assets via Embedded FS
	fileServer := http.FileServer(web.GetFileSystem())
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/api/") {
			http.NotFound(w, r)
			return
		}
		fileServer.ServeHTTP(w, r)
	})

	mux.HandleFunc("OPTIONS /", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Trace-ID")
		w.WriteHeader(http.StatusOK)
	})

	// Telemetry Middleware applied to all routes
	telemetryHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		traceID := r.Header.Get("X-Trace-ID")
		if traceID == "" {
			traceID = uuid.New().String()
		}
		w.Header().Set("X-Trace-ID", traceID)

		// Capture request payload copy for non-GET API requests
		var reqBody string
		if strings.HasPrefix(r.URL.Path, "/api/") && r.Method != http.MethodGet && r.Method != http.MethodOptions {
			bodyBytes, err := io.ReadAll(r.Body)
			if err == nil {
				r.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))
				if len(bodyBytes) < 65536 {
					reqBody = string(bodyBytes)
				} else {
					reqBody = fmt.Sprintf("[%d bytes payload]", len(bodyBytes))
				}
			}
		}

		recWriter := &statusRecordingResponseWriter{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}

		ctx := engine.ContextWithTrace(r.Context(), traceID, uuid.New().String()[:16])
		mux.ServeHTTP(recWriter, r.WithContext(ctx))

		duration := time.Since(start)

		// Record telemetry for API routes (exclude recursive telemetry stream)
		if strings.HasPrefix(r.URL.Path, "/api/") && r.URL.Path != "/api/telemetry/stream" {
			apiLog := engine.APIRequestLog{
				ID:                uuid.New().String(),
				Timestamp:         start.UTC(),
				Method:            r.Method,
				Path:              r.URL.Path,
				Status:            recWriter.statusCode,
				DurationUs:        duration.Microseconds(),
				DurationFormatted: engine.FormatDuration(duration),
				ClientIP:          r.RemoteAddr,
				BytesReceived:     int64(len(reqBody)),
				BytesSent:         recWriter.bytesWritten,
				TraceID:           traceID,
				RequestBody:       reqBody,
			}
			engine.GlobalTelemetry.RecordAPIRequest(apiLog)

			engine.GlobalTelemetry.RecordGoLog(engine.GoLogEntry{
				Timestamp: time.Now().UTC(),
				Level:     "INFO",
				Source:    "workbench.http",
				TraceID:   traceID,
				Message:   fmt.Sprintf("%s %s -> %d (%s)", r.Method, r.URL.Path, recWriter.statusCode, apiLog.DurationFormatted),
				Fields: map[string]any{
					"method":      r.Method,
					"path":        r.URL.Path,
					"status":      recWriter.statusCode,
					"duration_us": duration.Microseconds(),
					"bytes_sent":  recWriter.bytesWritten,
				},
			})
		}
	})

	addr := fmt.Sprintf(":%d", port)
	server := &http.Server{
		Addr:    addr,
		Handler: telemetryHandler,
	}

	go func() {
		fmt.Printf("\n┌─────────────────────────────────────────────────────────────┐\n")
		fmt.Printf("│  🚀 MODULE WORKBENCH & FLIGHT RECORDER ACTIVE               │\n")
		fmt.Printf("│  URL:     http://localhost:%-5d                            │\n", port)
		fmt.Printf("│  STORAGE: %-49s │\n", historyDir)
		fmt.Printf("└─────────────────────────────────────────────────────────────┘\n\n")

		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Fprintf(os.Stderr, "Server failed: %v\n", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	fmt.Println("\nGracefully shutting down workbench...")
	scanner.StopHotWatcher()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer shutdownCancel()
	_ = server.Shutdown(shutdownCtx)
	fmt.Println("Workbench stopped.")
	return nil
}

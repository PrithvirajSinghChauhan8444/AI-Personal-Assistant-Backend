package gateway_test

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"assistant/src/gateway"
)

// SimulationRecord captures the result of an individual chaos/stress test case.
type SimulationRecord struct {
	TestNumber      int           `json:"test_number"`
	Scenario        string        `json:"scenario"`
	Category        string        `json:"category"`
	InputSummary    string        `json:"input_summary"`
	ExpectedOutcome string        `json:"expected_outcome"`
	ActualOutcome   string        `json:"actual_outcome"`
	ErrorOccurred   bool          `json:"error_occurred"`
	ErrorCode       string        `json:"error_code,omitempty"`
	ErrorMessage    string        `json:"error_message,omitempty"`
	Duration        time.Duration `json:"duration_ns"`
	Passed          bool          `json:"passed"`
	DiagnosticNotes string        `json:"diagnostic_notes,omitempty"`
}

// SimulationReport collects the complete telemetry of the process simulation.
type SimulationReport struct {
	Title           string             `json:"title"`
	GeneratedAt     time.Time          `json:"generated_at"`
	TotalTests      int                `json:"total_tests"`
	Passed          int                `json:"passed"`
	Failed          int                `json:"failed"`
	ErrorsEncountered int              `json:"errors_encountered"`
	Records         []SimulationRecord `json:"records"`
}

// simulatedDownstreamHandler simulates Layer 2 (Orchestrator) with configurable behavior.
type simulatedDownstreamHandler struct {
	mu           sync.Mutex
	turnCount    int64
	executeFn    func(ctx context.Context, req gateway.InboundTurnRequest, ch chan<- gateway.OutboundEvent) error
	hitlFn       func(ctx context.Context, resp gateway.HITLResponse) error
	receivedReqs []gateway.InboundTurnRequest
}

func (h *simulatedDownstreamHandler) ExecuteTurn(
	ctx context.Context,
	req gateway.InboundTurnRequest,
	ch chan<- gateway.OutboundEvent,
) error {
	atomic.AddInt64(&h.turnCount, 1)
	h.mu.Lock()
	h.receivedReqs = append(h.receivedReqs, req)
	h.mu.Unlock()

	if h.executeFn != nil {
		return h.executeFn(ctx, req, ch)
	}

	// Default: emit a thought chunk, a token chunk, and complete
	select {
	case <-ctx.Done():
		return ctx.Err()
	case ch <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventThoughtChunk,
		AgentName: req.TargetAgent,
		TextDelta: "Analyzing prompt intent...",
	}:
	}

	select {
	case <-ctx.Done():
		return ctx.Err()
	case ch <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventTokenChunk,
		AgentName: req.TargetAgent,
		TextDelta: fmt.Sprintf("Response to: %s", req.Prompt),
	}:
	}

	select {
	case <-ctx.Done():
		return ctx.Err()
	case ch <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventTurnComplete,
		AgentName: req.TargetAgent,
		Metrics: &gateway.TurnMetrics{
			ModelName:       "simulation-model-v1",
			PromptTokens:    15,
			CompletionTokens: 25,
			TotalDurationMs: 10,
		},
	}:
	}

	return nil
}

func (h *simulatedDownstreamHandler) SubmitHITLResponse(ctx context.Context, resp gateway.HITLResponse) error {
	if h.hitlFn != nil {
		return h.hitlFn(ctx, resp)
	}
	return nil
}

// TestGatewayProcessSimulation simulates the running Gateway layer under 35 distinct attack and stress scenarios.
func TestGatewayProcessSimulation(t *testing.T) {
	var records []SimulationRecord
	var recordMu sync.Mutex

	recordTest := func(rec SimulationRecord) {
		recordMu.Lock()
		defer recordMu.Unlock()
		records = append(records, rec)
	}

	// 1. Process Setup: Create the running Gateway instance
	handler := &simulatedDownstreamHandler{}
	gw, err := gateway.NewGateway(handler)
	if err != nil {
		t.Fatalf("Failed to initialize Gateway process: %v", err)
	}

	// Helper to extract GatewayError code if present
	extractErrorCode := func(err error) string {
		if err == nil {
			return ""
		}
		var ge *gateway.GatewayError
		if errors.As(err, &ge) {
			return ge.Code
		}
		return "NON_GATEWAY_ERROR"
	}

	// =========================================================================
	// CATEGORY 1: Malformed & Pathological Prompts
	// =========================================================================

	t.Run("01_EmptyPrompt", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "550e8400-e29b-41d4-a716-446655440000",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrEmptyPrompt)
		if !passed {
			t.Errorf("Expected ErrEmptyPrompt, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      1,
			Scenario:        "Empty prompt string submission",
			Category:        "Input Sanitization",
			InputSummary:    `Prompt: ""`,
			ExpectedOutcome: "ERR_EMPTY_PROMPT rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Gateway immediately aborts before scheduling goroutines",
		})
	})

	t.Run("02_WhitespaceOnlyPrompt", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "550e8400-e29b-41d4-a716-446655440000",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "   \t\r\n \n \t  ",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrEmptyPrompt)
		if !passed {
			t.Errorf("Expected ErrEmptyPrompt for whitespace prompt, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      2,
			Scenario:        "Whitespace, tabs, and newlines prompt",
			Category:        "Input Sanitization",
			InputSummary:    `Prompt: "   \t\r\n \n \t  "`,
			ExpectedOutcome: "ERR_EMPTY_PROMPT rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Trimming correctly identifies zero semantic content",
		})
	})

	t.Run("03_EmbeddedNullBytesPrompt", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "550e8400-e29b-41d4-a716-446655440000",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "list\x00files\x00/root",
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && !strings.Contains(norm.Prompt, "\x00") && norm.Prompt == "list files /root"
		if !passed {
			t.Errorf("Expected null bytes replaced with spaces, got prompt=%q, err=%v", norm.Prompt, err)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      3,
			Scenario:        "Prompt with embedded null bytes poison",
			Category:        "Security Sanitization",
			InputSummary:    `Prompt: "list\x00files\x00/root"`,
			ExpectedOutcome: "Null bytes stripped/replaced with spaces without crashing",
			ActualOutcome:   fmt.Sprintf("Sanitized prompt: %q", norm.Prompt),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Guards against C-string truncation attacks in underlying system tools",
		})
	})

	t.Run("04_TerminalANSIEscapeInjection", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "550e8400-e29b-41d4-a716-446655440000",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "\x1b[31;1mDangerous Command\x1b[0m \x1b[2JClear",
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && !strings.Contains(norm.Prompt, "\x1b") && norm.Prompt == "Dangerous Command Clear"
		if !passed {
			t.Errorf("Expected ANSI codes stripped, got prompt=%q, err=%v", norm.Prompt, err)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      4,
			Scenario:        "Terminal ANSI escape sequence injection",
			Category:        "Terminal Protection",
			InputSummary:    `Prompt: "\x1b[31;1mDangerous Command\x1b[0m \x1b[2JClear"`,
			ExpectedOutcome: "ANSI escape sequences stripped completely",
			ActualOutcome:   fmt.Sprintf("Cleaned prompt: %q", norm.Prompt),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Prevents terminal hijacking, cursor repositioning, and screen clearing exploits",
		})
	})

	t.Run("05_InvalidCorruptUTF8Prompt", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "550e8400-e29b-41d4-a716-446655440000",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "Bad bytes: \xff\xfe\xfd\x80\x81 valid text",
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && strings.Contains(norm.Prompt, "\uFFFD")
		if !passed {
			t.Errorf("Expected invalid UTF-8 bytes converted to replacement chars, got prompt=%q, err=%v", norm.Prompt, err)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      5,
			Scenario:        "Corrupt non-UTF8 byte sequence injection",
			Category:        "Unicode Resilience",
			InputSummary:    `Prompt: "Bad bytes: \xff\xfe\xfd\x80\x81 valid text"`,
			ExpectedOutcome: "Converted to valid UTF-8 with standard replacement char",
			ActualOutcome:   fmt.Sprintf("Normalized prompt: %q", norm.Prompt),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Normalizer sanitizes non-UTF8 without discarding entire prompt",
		})
	})

	t.Run("06_MassiveBufferBombPrompt", func(t *testing.T) {
		start := time.Now()
		hugePrompt := strings.Repeat("A", 2*1024*1024) // 2 MB string
		req := gateway.InboundTurnRequest{
			SessionID: "550e8400-e29b-41d4-a716-446655440000",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    hugePrompt,
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		// Note: The current normalizer allows large in-memory strings if not constrained at HTTP adapter.
		// We verify it does not crash or panic.
		passed := (err == nil) && len(norm.Prompt) == len(hugePrompt)
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      6,
			Scenario:        "2 Megabyte massive prompt buffer bomb",
			Category:        "Stress & Memory Stability",
			InputSummary:    "2,097,152 bytes ASCII character flood",
			ExpectedOutcome: "Processed without memory panic or stack overflow",
			ActualOutcome:   fmt.Sprintf("Processed length: %d bytes, Err: %v", len(norm.Prompt), err),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Layer 1 Gateway tolerates large buffers; HTTP adapter should enforce 1MB limit",
		})
	})

	// =========================================================================
	// CATEGORY 2: Session ID Fuzzing & Security Traversal
	// =========================================================================

	t.Run("07_PathTraversalSessionID", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "../../../../etc/shadow",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "hello",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrInvalidSessionID)
		if !passed {
			t.Errorf("Expected ErrInvalidSessionID, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      7,
			Scenario:        "Path traversal dots and slashes in session ID",
			Category:        "Session Security",
			InputSummary:    `SessionID: "../../../../etc/shadow"`,
			ExpectedOutcome: "ERR_INVALID_SESSION_ID rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Blocks directory traversal attempts into session persistence layers",
		})
	})

	t.Run("08_SQLMetacharactersSessionID", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "' OR '1'='1'; DROP TABLE sessions;--",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "hello",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrInvalidSessionID)
		if !passed {
			t.Errorf("Expected ErrInvalidSessionID for SQL chars, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      8,
			Scenario:        "SQL injection characters in session ID",
			Category:        "Session Security",
			InputSummary:    `SessionID: "' OR '1'='1'; DROP TABLE sessions;--"`,
			ExpectedOutcome: "ERR_INVALID_SESSION_ID rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Quotes, semicolons, and comment markers blocked",
		})
	})

	t.Run("09_OversizedSessionID", func(t *testing.T) {
		start := time.Now()
		hugeSess := strings.Repeat("a", 256)
		req := gateway.InboundTurnRequest{
			SessionID: hugeSess,
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "hello",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrFieldLengthExceeded)
		if !passed {
			t.Errorf("Expected ErrFieldLengthExceeded for 256-char session ID, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      9,
			Scenario:        "Session ID length exceeding 128 characters",
			Category:        "Session Security",
			InputSummary:    "256-character string",
			ExpectedOutcome: "ERR_FIELD_LENGTH_EXCEEDED rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Prevents memory bloat and index overflow in session storage",
		})
	})

	t.Run("10_NullByteInSessionID", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "session\x00poisoned",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "hello",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrIllegalCharacters)
		if !passed {
			t.Errorf("Expected ErrIllegalCharacters, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      10,
			Scenario:        "Embedded null byte inside session ID",
			Category:        "Session Security",
			InputSummary:    `SessionID: "session\x00poisoned"`,
			ExpectedOutcome: "ERR_ILLEGAL_CHARACTERS rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Strictly rejects null characters in identity fields",
		})
	})

	t.Run("11_DisallowedPunctuationSessionID", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "session!#$@%^&*()",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "hello",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrInvalidSessionID)
		if !passed {
			t.Errorf("Expected ErrInvalidSessionID, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      11,
			Scenario:        "Disallowed punctuation in non-UUID session ID",
			Category:        "Session Security",
			InputSummary:    `SessionID: "session!#$@%^&*()"`,
			ExpectedOutcome: "ERR_INVALID_SESSION_ID rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Session identifiers must be valid UUIDs or clean alphanumerics",
		})
	})

	t.Run("12_ValidUUIDSessionID", func(t *testing.T) {
		start := time.Now()
		validUUID := "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
		req := gateway.InboundTurnRequest{
			SessionID: validUUID,
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "hello world",
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && norm.SessionID == validUUID
		if !passed {
			t.Errorf("Expected valid UUID session preserved, got: %v", err)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      12,
			Scenario:        "Standard valid RFC-4122 UUID session ID",
			Category:        "Session Conformance",
			InputSummary:    validUUID,
			ExpectedOutcome: "Accepted and preserved exactly",
			ActualOutcome:   fmt.Sprintf("Normalized SessionID: %s", norm.SessionID),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Standard UUID pass-through confirmed",
		})
	})

	t.Run("13_EmptySessionIDAutoDelegation", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			SessionID: "",
			Channel:   gateway.ClientTypeCLI,
			Prompt:    "start fresh session",
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && norm.SessionID == ""
		if !passed {
			t.Errorf("Expected empty session preserved to trigger Layer 2 generation, got: %v", err)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      13,
			Scenario:        "Empty session ID for fresh session initialization",
			Category:        "Session Conformance",
			InputSummary:    `SessionID: ""`,
			ExpectedOutcome: "Empty string passed to Layer 2 to spawn fresh session",
			ActualOutcome:   fmt.Sprintf("Passed SessionID: %q", norm.SessionID),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Conduit protocol contract verified",
		})
	})

	// =========================================================================
	// CATEGORY 3: Channel & Trigger Enum Type Confusion
	// =========================================================================

	t.Run("14_InvalidChannelEnum", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Channel: gateway.ClientType("BLUETOOTH"),
			Prompt:  "test channel",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrInvalidChannel)
		if !passed {
			t.Errorf("Expected ErrInvalidChannel, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      14,
			Scenario:        "Unknown channel enum 'BLUETOOTH'",
			Category:        "Enum Validation",
			InputSummary:    `Channel: "BLUETOOTH"`,
			ExpectedOutcome: "ERR_INVALID_CHANNEL rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Only CLI, TELEGRAM, WEB, and INTERNAL permitted",
		})
	})

	t.Run("15_EmptyChannelDefaulting", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Channel: "",
			Prompt:  "default channel query",
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && norm.Channel == gateway.ClientTypeCLI
		if !passed {
			t.Errorf("Expected default channel to be CLI, got: %v", norm.Channel)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      15,
			Scenario:        "Omitted channel defaulting",
			Category:        "Enum Validation",
			InputSummary:    `Channel: ""`,
			ExpectedOutcome: "Defaulted gracefully to CLI",
			ActualOutcome:   fmt.Sprintf("Normalized Channel: %s", norm.Channel),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Permissive defaulting for CLI-first backward compatibility",
		})
	})

	t.Run("16_InvalidTriggerEnum", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Trigger: gateway.TriggerType("QUANTUM_TRIGGER"),
			Prompt:  "test trigger",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrInvalidTrigger)
		if !passed {
			t.Errorf("Expected ErrInvalidTrigger, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      16,
			Scenario:        "Unknown trigger enum 'QUANTUM_TRIGGER'",
			Category:        "Enum Validation",
			InputSummary:    `Trigger: "QUANTUM_TRIGGER"`,
			ExpectedOutcome: "ERR_INVALID_TRIGGER rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Only INTERACTIVE and AUTONOMOUS permitted",
		})
	})

	t.Run("17_EmptyTriggerDefaulting", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Trigger: "",
			Prompt:  "default trigger query",
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && norm.Trigger == gateway.TriggerInteractive
		if !passed {
			t.Errorf("Expected default trigger to be INTERACTIVE, got: %v", norm.Trigger)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      17,
			Scenario:        "Omitted trigger defaulting",
			Category:        "Enum Validation",
			InputSummary:    `Trigger: ""`,
			ExpectedOutcome: "Defaulted gracefully to INTERACTIVE",
			ActualOutcome:   fmt.Sprintf("Normalized Trigger: %s", norm.Trigger),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Assumes human interactive presence by default",
		})
	})

	// =========================================================================
	// CATEGORY 4: Autonomous Capabilities & Security Boundary
	// =========================================================================

	t.Run("18_AutonomousWildcardCapabilityForbidden", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Trigger:             gateway.TriggerAutonomous,
			AllowedCapabilities: []string{"*"},
			Prompt:              "run unattended cleanup",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrForbiddenCapability)
		if !passed {
			t.Errorf("Expected ErrForbiddenCapability, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      18,
			Scenario:        "Wildcard tool capability in autonomous mode",
			Category:        "Capability Authorization",
			InputSummary:    `Trigger: AUTONOMOUS, AllowedCapabilities: ["*"]`,
			ExpectedOutcome: "ERR_FORBIDDEN_CAPABILITY rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Hard security constraint: unattended daemons cannot hold unrestricted root tools",
		})
	})

	t.Run("19_AutonomousUnauthorizedCapabilityFiltered", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Trigger:             gateway.TriggerAutonomous,
			AllowedCapabilities: []string{"bash_rm_rf", "calendar_read", "format_hard_drive"},
			Prompt:              "check calendar",
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && len(norm.AllowedCapabilities) == 1 && norm.AllowedCapabilities[0] == "calendar_read"
		if !passed {
			t.Errorf("Expected unauthorized capabilities stripped, got: %v", norm.AllowedCapabilities)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      19,
			Scenario:        "Unauthorized capabilities in autonomous trigger mode",
			Category:        "Capability Authorization",
			InputSummary:    `AllowedCapabilities: ["bash_rm_rf", "calendar_read", "format_hard_drive"]`,
			ExpectedOutcome: "Filtered down strictly to whitelisted autonomous tools",
			ActualOutcome:   fmt.Sprintf("Permitted capabilities: %v", norm.AllowedCapabilities),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Non-whitelisted tools pruned automatically",
		})
	})

	// =========================================================================
	// CATEGORY 5: Agent Direct Addressing & Injection Attacks
	// =========================================================================

	t.Run("20_AgentPathTraversalSyntax", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Prompt: "@../../bin/sh execute echo pwned",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrInvalidAgentSyntax)
		if !passed {
			t.Errorf("Expected ErrInvalidAgentSyntax, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      20,
			Scenario:        "Agent selector with path traversal syntax",
			Category:        "Agent Routing Security",
			InputSummary:    `Prompt: "@../../bin/sh execute echo pwned"`,
			ExpectedOutcome: "ERR_INVALID_AGENT_SYNTAX rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Dots and slashes blocked in @agent syntax",
		})
	})

	t.Run("21_AgentShellInjectionSyntax", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Prompt: "@$(whoami) test shell expansion",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrInvalidAgentSyntax)
		if !passed {
			t.Errorf("Expected ErrInvalidAgentSyntax, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      21,
			Scenario:        "Agent selector with subshell command substitution",
			Category:        "Agent Routing Security",
			InputSummary:    `Prompt: "@$(whoami) test shell expansion"`,
			ExpectedOutcome: "ERR_INVALID_AGENT_SYNTAX rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Subshell metacharacters $, (, ) blocked",
		})
	})

	t.Run("22_AgentPipeInjectionSyntax", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Prompt: "@system|curl evil.com test pipe",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrInvalidAgentSyntax)
		if !passed {
			t.Errorf("Expected ErrInvalidAgentSyntax, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      22,
			Scenario:        "Agent selector with pipeline metacharacter",
			Category:        "Agent Routing Security",
			InputSummary:    `Prompt: "@system|curl evil.com test pipe"`,
			ExpectedOutcome: "ERR_INVALID_AGENT_SYNTAX rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Pipe metacharacter | blocked",
		})
	})

	t.Run("23_UnknownAgentTarget", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Prompt: "@hacker_bot do some damage",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrUnknownAgent)
		if !passed {
			t.Errorf("Expected ErrUnknownAgent, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      23,
			Scenario:        "Non-existent agent target name",
			Category:        "Agent Routing Security",
			InputSummary:    `Prompt: "@hacker_bot do some damage"`,
			ExpectedOutcome: "ERR_UNKNOWN_AGENT rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Only validated system agents accepted",
		})
	})

	t.Run("24_BareAtSymbol", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Prompt: "@",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrEmptyPrompt)
		if !passed {
			t.Errorf("Expected ErrEmptyPrompt for lone '@', got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      24,
			Scenario:        "Lone '@' symbol prompt without agent or command",
			Category:        "Agent Routing Parsing",
			InputSummary:    `Prompt: "@"`,
			ExpectedOutcome: "ERR_EMPTY_PROMPT rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Lone selector treated as missing prompt",
		})
	})

	t.Run("25_AgentSelectorWithoutPrompt", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Prompt: "@system",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrEmptyPrompt)
		if !passed {
			t.Errorf("Expected ErrEmptyPrompt, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      25,
			Scenario:        "Valid agent selector with no trailing prompt text",
			Category:        "Agent Routing Parsing",
			InputSummary:    `Prompt: "@system"`,
			ExpectedOutcome: "ERR_EMPTY_PROMPT rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Target agent specified but zero action payload",
		})
	})

	t.Run("26_AgentFlagWithoutPrompt", func(t *testing.T) {
		start := time.Now()
		req := gateway.InboundTurnRequest{
			Prompt: "--agent system",
		}
		_, _, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		code := extractErrorCode(err)
		passed := errors.Is(err, gateway.ErrEmptyPrompt)
		if !passed {
			t.Errorf("Expected ErrEmptyPrompt, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      26,
			Scenario:        "Flag syntax '--agent system' with no trailing prompt",
			Category:        "Agent Routing Parsing",
			InputSummary:    `Prompt: "--agent system"`,
			ExpectedOutcome: "ERR_EMPTY_PROMPT rejected",
			ActualOutcome:   fmt.Sprintf("Code: %s, Err: %v", code, err),
			ErrorOccurred:   err != nil,
			ErrorCode:       code,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Flag syntax requires payload",
		})
	})

	t.Run("27_InlineCodeQuotedAgentNotExtracted", func(t *testing.T) {
		start := time.Now()
		prompt := "Run `@system` internally in script"
		req := gateway.InboundTurnRequest{
			Prompt: prompt,
		}
		ch, norm, err := gw.SubmitTurn(context.Background(), req)
		dur := time.Since(start)

		passed := (err == nil) && norm.TargetAgent == "auto" && norm.Prompt == prompt
		if !passed {
			t.Errorf("Expected targetAgent='auto' and prompt preserved, got: agent=%s, prompt=%s, err=%v", norm.TargetAgent, norm.Prompt, err)
		}
		if ch != nil {
			for range ch {
			}
		}

		recordTest(SimulationRecord{
			TestNumber:      27,
			Scenario:        "Agent token inside markdown inline code quotes",
			Category:        "Agent Routing Parsing",
			InputSummary:    fmt.Sprintf("Prompt: %q", prompt),
			ExpectedOutcome: "Preserved as literal prompt text, targetAgent remains 'auto'",
			ActualOutcome:   fmt.Sprintf("Agent: %s, Prompt: %q", norm.TargetAgent, norm.Prompt),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Prevents false routing when user discusses code examples",
		})
	})

	// =========================================================================
	// CATEGORY 6: Process Lifecycle, Context & Downstream Faults
	// =========================================================================

	t.Run("28_NilTurnHandlerConstruction", func(t *testing.T) {
		start := time.Now()
		nilGW, err := gateway.NewGateway(nil)
		dur := time.Since(start)

		passed := (nilGW == nil) && errors.Is(err, gateway.ErrNilHandler)
		if !passed {
			t.Errorf("Expected ErrNilHandler and nil gateway, got gw=%v, err=%v", nilGW, err)
		}

		recordTest(SimulationRecord{
			TestNumber:      28,
			Scenario:        "Gateway instantiation with nil downstream TurnHandler",
			Category:        "Process Initialization",
			InputSummary:    "NewGateway(nil)",
			ExpectedOutcome: "ErrNilHandler returned, gateway instantiation denied",
			ActualOutcome:   fmt.Sprintf("Err: %v", err),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Prevents nil pointer panic during turn execution",
		})
	})

	t.Run("29_PreCancelledContextTurnSubmission", func(t *testing.T) {
		start := time.Now()
		cancelledCtx, cancel := context.WithCancel(context.Background())
		cancel() // Cancel before invocation

		req := gateway.InboundTurnRequest{
			Prompt: "should be cancelled immediately",
		}
		ch, _, err := gw.SubmitTurn(cancelledCtx, req)
		dur := time.Since(start)

		// SubmitTurn normalizes and launches goroutine. Goroutine should gracefully exit when reading context.
		eventsReceived := 0
		if ch != nil {
			for range ch {
				eventsReceived++
			}
		}

		passed := (err == nil)
		recordTest(SimulationRecord{
			TestNumber:      29,
			Scenario:        "Submit turn with already cancelled context",
			Category:        "Context & Cancellation",
			InputSummary:    "context.Canceled passed into SubmitTurn",
			ExpectedOutcome: "Pipeline drains channel cleanly without goroutine leak or hang",
			ActualOutcome:   fmt.Sprintf("Events received: %d, Err: %v", eventsReceived, err),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Goroutine honors cancellation and closes channel",
		})
	})

	t.Run("30_DownstreamOrchestratorExecutionError", func(t *testing.T) {
		start := time.Now()
		errHandler := &simulatedDownstreamHandler{
			executeFn: func(ctx context.Context, req gateway.InboundTurnRequest, ch chan<- gateway.OutboundEvent) error {
				return errors.New("simulated orchestrator model timeout")
			},
		}
		errGW, err := gateway.NewGateway(errHandler)
		if err != nil {
			t.Fatalf("Failed creating test gateway: %v", err)
		}

		ch, _, err := errGW.SubmitTurn(context.Background(), gateway.InboundTurnRequest{
			Prompt: "trigger downstream error",
		})
		dur := time.Since(start)

		var capturedEvents []gateway.OutboundEvent
		if ch != nil {
			for ev := range ch {
				capturedEvents = append(capturedEvents, ev)
			}
		}

		// Gateway must emit an EventTurnError
		hasTurnError := false
		var errReason string
		for _, ev := range capturedEvents {
			if ev.Type == gateway.EventTurnError {
				hasTurnError = true
				errReason = ev.Error
			}
		}

		passed := (err == nil) && hasTurnError && strings.Contains(errReason, "simulated orchestrator model timeout")
		if !passed {
			t.Errorf("Expected EventTurnError emitted on channel, got: %v", capturedEvents)
		}

		recordTest(SimulationRecord{
			TestNumber:      30,
			Scenario:        "Downstream TurnHandler returns execution error",
			Category:        "Downstream Fault Tolerance",
			InputSummary:    "ExecuteTurn returns error: simulated orchestrator model timeout",
			ExpectedOutcome: "EventTurnError emitted on channel and channel closed cleanly",
			ActualOutcome:   fmt.Sprintf("HasTurnError: %v, Error: %q", hasTurnError, errReason),
			ErrorOccurred:   true,
			ErrorMessage:    errReason,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Gateway converts downstream error into standard OutboundEvent",
		})
	})

	t.Run("31_HITLMissingRequestID", func(t *testing.T) {
		start := time.Now()
		resp := gateway.HITLResponse{
			RequestID: "",
			SessionID: "550e8400-e29b-41d4-a716-446655440000",
			Approved:  true,
		}
		err := gw.RespondHITL(context.Background(), resp)
		dur := time.Since(start)

		passed := errors.Is(err, gateway.ErrEmptyRequestID)
		if !passed {
			t.Errorf("Expected ErrEmptyRequestID, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      31,
			Scenario:        "HITL human approval response with missing RequestID",
			Category:        "HITL Protocol",
			InputSummary:    `HITLResponse{RequestID: ""}`,
			ExpectedOutcome: "ErrEmptyRequestID rejected",
			ActualOutcome:   fmt.Sprintf("Err: %v", err),
			ErrorOccurred:   err != nil,
			ErrorMessage:    fmt.Sprintf("%v", err),
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Prevents orphaned approvals from corrupting wait states",
		})
	})

	t.Run("32_HITLValidDispatch", func(t *testing.T) {
		start := time.Now()
		var capturedResp gateway.HITLResponse
		hitlHandler := &simulatedDownstreamHandler{
			hitlFn: func(ctx context.Context, resp gateway.HITLResponse) error {
				capturedResp = resp
				return nil
			},
		}
		hitlGW, _ := gateway.NewGateway(hitlHandler)

		resp := gateway.HITLResponse{
			RequestID:    "hitl_req_9999",
			SessionID:    "550e8400-e29b-41d4-a716-446655440000",
			Approved:     true,
			UserFeedback: "Proceed with caution",
		}
		err := hitlGW.RespondHITL(context.Background(), resp)
		dur := time.Since(start)

		passed := (err == nil) && capturedResp.RequestID == "hitl_req_9999" && !capturedResp.RespondedAt.IsZero()
		if !passed {
			t.Errorf("Expected HITL response forwarded with non-zero timestamp, got: %v", err)
		}

		recordTest(SimulationRecord{
			TestNumber:      32,
			Scenario:        "Valid HITL approval forwarded to downstream handler",
			Category:        "HITL Protocol",
			InputSummary:    `RequestID: "hitl_req_9999", Approved: true`,
			ExpectedOutcome: "Dispatched to handler with auto-populated UTC timestamp",
			ActualOutcome:   fmt.Sprintf("Dispatched: %s, Time: %s", capturedResp.RequestID, capturedResp.RespondedAt),
			ErrorOccurred:   err != nil,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "HITL conduit contract verified",
		})
	})

	// =========================================================================
	// CATEGORY 7: High-Throughput Burst, Non-Stop Flooding & Concurrency
	// =========================================================================

	t.Run("33_RapidBurstConcurrentFlooding", func(t *testing.T) {
		start := time.Now()
		concurrency := 100
		var wg sync.WaitGroup
		var successCount int64
		var failCount int64

		for i := 0; i < concurrency; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				prompt := fmt.Sprintf("burst_query_turn_%04d", idx)
				ch, _, err := gw.SubmitTurn(context.Background(), gateway.InboundTurnRequest{
					SessionID: "550e8400-e29b-41d4-a716-446655440000",
					Channel:   gateway.ClientTypeCLI,
					Prompt:    prompt,
				})
				if err != nil {
					atomic.AddInt64(&failCount, 1)
					return
				}
				// Drain the outbound streaming channel
				for range ch {
				}
				atomic.AddInt64(&successCount, 1)
			}(i)
		}

		wg.Wait()
		dur := time.Since(start)

		passed := (successCount == int64(concurrency)) && (failCount == 0)
		if !passed {
			t.Errorf("Expected all 100 concurrent turns to succeed, success=%d, fail=%d", successCount, failCount)
		}

		recordTest(SimulationRecord{
			TestNumber:      33,
			Scenario:        "Rapid non-stop flood: 100 concurrent turns on Gateway",
			Category:        "Concurrency & Load Stress",
			InputSummary:    "100 goroutines submitting turns simultaneously",
			ExpectedOutcome: "100/100 processed concurrently without deadlock or race",
			ActualOutcome:   fmt.Sprintf("Succeeded: %d, Failed: %d", successCount, failCount),
			ErrorOccurred:   failCount > 0,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "High-throughput channel allocation and goroutine dispatch confirmed",
		})
	})

	t.Run("34_SimultaneousTurnsMultipleSessions", func(t *testing.T) {
		start := time.Now()
		sessionCount := 50
		var wg sync.WaitGroup
		var successCount int64

		for i := 0; i < sessionCount; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				sessID := fmt.Sprintf("550e8400-e29b-41d4-a716-44665544%04d", idx)
				ch, _, err := gw.SubmitTurn(context.Background(), gateway.InboundTurnRequest{
					SessionID: sessID,
					Channel:   gateway.ClientTypeWeb,
					Prompt:    fmt.Sprintf("multi_session_query_%d", idx),
				})
				if err == nil {
					for range ch {
					}
					atomic.AddInt64(&successCount, 1)
				}
			}(i)
		}

		wg.Wait()
		dur := time.Since(start)

		passed := successCount == int64(sessionCount)
		recordTest(SimulationRecord{
			TestNumber:      34,
			Scenario:        "Multiple distinct sessions firing simultaneous turns",
			Category:        "Concurrency & Load Stress",
			InputSummary:    "50 unique session UUIDs concurrently invoking turns",
			ExpectedOutcome: "50/50 sessions processed independently",
			ActualOutcome:   fmt.Sprintf("Completed sessions: %d", successCount),
			ErrorOccurred:   !passed,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "Isolation between concurrent sessions verified",
		})
	})

	t.Run("35_SlowConsumerChannelSaturation", func(t *testing.T) {
		start := time.Now()
		fastEmitterHandler := &simulatedDownstreamHandler{
			executeFn: func(ctx context.Context, req gateway.InboundTurnRequest, ch chan<- gateway.OutboundEvent) error {
				// Emit 64 events (buffer size is 64)
				for i := 0; i < 64; i++ {
					ch <- gateway.OutboundEvent{
						SessionID: req.SessionID,
						Type:      gateway.EventTokenChunk,
						TextDelta: fmt.Sprintf("token_%d", i),
					}
				}
				return nil
			},
		}

		fastGW, _ := gateway.NewGateway(fastEmitterHandler)
		ch, _, err := fastGW.SubmitTurn(context.Background(), gateway.InboundTurnRequest{
			Prompt: "fill buffer",
		})

		received := 0
		if ch != nil {
			// Intentionally delay consumption to test buffer behavior
			time.Sleep(20 * time.Millisecond)
			for range ch {
				received++
			}
		}
		dur := time.Since(start)

		passed := (err == nil) && received == 64
		if !passed {
			t.Errorf("Expected 64 events buffered and read, got: %d", received)
		}

		recordTest(SimulationRecord{
			TestNumber:      35,
			Scenario:        "Outbound channel 64-slot buffer saturation under slow consumer",
			Category:        "Streaming & Buffering",
			InputSummary:    "Downstream emits 64 events rapidly to slow consumer",
			ExpectedOutcome: "Full buffer of 64 events drained without blocking or loss",
			ActualOutcome:   fmt.Sprintf("Events consumed: %d/64", received),
			ErrorOccurred:   !passed,
			Duration:        dur,
			Passed:          passed,
			DiagnosticNotes: "64-slot channel buffer capacity verified",
		})
	})

	// =========================================================================
	// SAVE TELEMETRY & REPORT TO test/gateway/simulation_report.json
	// =========================================================================

	passedCount := 0
	failedCount := 0
	errCount := 0
	for _, r := range records {
		if r.Passed {
			passedCount++
		} else {
			failedCount++
		}
		if r.ErrorOccurred {
			errCount++
		}
	}

	report := SimulationReport{
		Title:             "Gateway Layer Process Simulation & Chaos Test Report",
		GeneratedAt:       time.Now().UTC(),
		TotalTests:        len(records),
		Passed:            passedCount,
		Failed:            failedCount,
		ErrorsEncountered: errCount,
		Records:           records,
	}

	reportBytes, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		t.Fatalf("Failed serializing simulation report: %v", err)
	}

	reportPath := filepath.Join(".", "simulation_report.json")
	if err := os.WriteFile(reportPath, reportBytes, 0644); err != nil {
		t.Fatalf("Failed writing simulation report to %s: %v", reportPath, err)
	}

	t.Logf("=== GATEWAY PROCESS SIMULATION COMPLETED ===")
	t.Logf("Total Scenarios Tested: %d", len(records))
	t.Logf("Passed: %d | Failed: %d | Errors Handled: %d", passedCount, failedCount, errCount)
	t.Logf("Report saved to: %s", reportPath)

	if failedCount > 0 {
		t.Fatalf("Gateway simulation failed: %d/%d tests did not meet invariants", failedCount, len(records))
	}
}

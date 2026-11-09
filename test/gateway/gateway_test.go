package gateway_test

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"assistant/src/gateway"
)

// ManualInputCase defines the structure for user-provided manual testing inputs.
type ManualInputCase struct {
	ID                  string                `json:"id"`
	Description         string                `json:"description,omitempty"`
	Type                string                `json:"type,omitempty"` // "turn" (default) or "hitl"
	Prompt              string                `json:"prompt,omitempty"`
	SessionID           string                `json:"session_id,omitempty"`
	UserID              string                `json:"user_id,omitempty"`
	Channel             string                `json:"channel,omitempty"`
	Trigger             string                `json:"trigger,omitempty"`
	AllowedCapabilities []string              `json:"allowed_capabilities,omitempty"`
	TargetAgent         string                `json:"target_agent,omitempty"`
	HITLResponse        *gateway.HITLResponse `json:"hitl_response,omitempty"`
	TimeoutMs           int64                 `json:"timeout_ms,omitempty"`
}

// ManualOutputCase records the raw, unadulterated reality produced by the Gateway.
// It does not judge, filter, assert, or alter the output in any way.
type ManualOutputCase struct {
	ID                     string                     `json:"id"`
	Description            string                     `json:"description,omitempty"`
	Type                   string                     `json:"type"`
	InputRaw               ManualInputCase            `json:"input_raw"`
	DispatchedToGateway    bool                       `json:"dispatched_to_gateway"`
	NormalizedRequest      *gateway.InboundTurnRequest `json:"normalized_request,omitempty"`
	StreamedOutboundEvents []gateway.OutboundEvent    `json:"streamed_outbound_events,omitempty"`
	ErrorOccurred          bool                       `json:"error_occurred"`
	ErrorCode              string                     `json:"error_code,omitempty"`
	ErrorMessage           string                     `json:"error_message,omitempty"`
	PanicOccurred          bool                       `json:"panic_occurred"`
	PanicMessage           string                     `json:"panic_message,omitempty"`
	ExecutionDurationMs    float64                    `json:"execution_duration_ms"`
}

// ManualTestingReport captures the top-level flight recorder log.
type ManualTestingReport struct {
	Title                    string             `json:"title"`
	ExecutedAt               time.Time          `json:"executed_at"`
	InputFile                string             `json:"input_file"`
	OutputFile               string             `json:"output_file"`
	TotalCasesRun            int                `json:"total_cases_run"`
	SuccessfulDispatches     int                `json:"successful_dispatches"`
	GatewayErrorsEncountered int                `json:"gateway_errors_encountered"`
	PanicsEncountered        int                `json:"panics_encountered"`
	Results                  []ManualOutputCase `json:"results"`
}

// realisticDownstreamMock simulates Layer 2 (Orchestrator) for manual testing.
type realisticDownstreamMock struct {
	lastHITLResponse gateway.HITLResponse
}

func (m *realisticDownstreamMock) ExecuteTurn(
	ctx context.Context,
	req gateway.InboundTurnRequest,
	eventCh chan<- gateway.OutboundEvent,
) error {
	// Emit reasoning thought chunk
	select {
	case <-ctx.Done():
		return ctx.Err()
	case eventCh <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventThoughtChunk,
		AgentName: req.TargetAgent,
		TextDelta: fmt.Sprintf("Downstream received prompt for target '%s'", req.TargetAgent),
	}:
	}

	// Emit streaming token chunk
	select {
	case <-ctx.Done():
		return ctx.Err()
	case eventCh <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventTokenChunk,
		AgentName: req.TargetAgent,
		TextDelta: fmt.Sprintf("Processed turn payload: %s", req.Prompt),
	}:
	}

	// Emit turn completion with metrics
	select {
	case <-ctx.Done():
		return ctx.Err()
	case eventCh <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      gateway.EventTurnComplete,
		AgentName: req.TargetAgent,
		Metrics: &gateway.TurnMetrics{
			ModelName:       "manual-testbench-model",
			PromptTokens:    int32(len(req.Prompt) / 4),
			CompletionTokens: 20,
			TotalDurationMs: 5,
		},
	}:
	}

	return nil
}

func (m *realisticDownstreamMock) SubmitHITLResponse(ctx context.Context, resp gateway.HITLResponse) error {
	m.lastHITLResponse = resp
	return nil
}

// TestManualGatewayInputs executes all inputs from manual_testing_input.json directly against Gateway,
// records the exact outputs without modifying them, and writes manual_testing_actual_output.json.
func TestManualGatewayInputs(t *testing.T) {
	inputFile := findInputFile()
	if inputFile == "" {
		t.Fatalf("Could not locate 'manual_testing_input.json'. Please create it in test/gateway/.")
	}

	rawBytes, err := os.ReadFile(inputFile)
	if err != nil {
		t.Fatalf("Failed reading manual input file %s: %v", inputFile, err)
	}

	testCases, err := parseInputCases(rawBytes)
	if err != nil {
		t.Fatalf("Failed parsing %s: %v", inputFile, err)
	}

	if len(testCases) == 0 {
		t.Logf("Warning: %s contains 0 test cases.", inputFile)
		return
	}

	// Instantiate the real Layer 1 Gateway with downstream mock
	downstream := &realisticDownstreamMock{}
	gw, err := gateway.NewGateway(downstream)
	if err != nil {
		t.Fatalf("Failed initializing Gateway: %v", err)
	}

	var results []ManualOutputCase
	successCount := 0
	errorCount := 0
	panicCount := 0

	for idx, tc := range testCases {
		if tc.ID == "" {
			tc.ID = fmt.Sprintf("CASE_%03d", idx+1)
		}

		t.Run(tc.ID, func(subT *testing.T) {
			record := executeSingleManualCase(tc, gw)
			results = append(results, record)

			if record.PanicOccurred {
				panicCount++
				subT.Logf("[%s] PANIC: %s", tc.ID, record.PanicMessage)
			} else if record.ErrorOccurred {
				errorCount++
				subT.Logf("[%s] REJECTED (Code=%s): %s", tc.ID, record.ErrorCode, record.ErrorMessage)
			} else {
				successCount++
				subT.Logf("[%s] ACCEPTED: Dispatched to Gateway, streamed %d events", tc.ID, len(record.StreamedOutboundEvents))
			}
		})
	}

	// Write the pure, unadulterated reality to manual_testing_actual_output.json
	outputPath := filepath.Join(filepath.Dir(inputFile), "manual_testing_actual_output.json")
	report := ManualTestingReport{
		Title:                    "Layer 1 Gateway - Manual Testing Actual Output Recording",
		ExecutedAt:               time.Now().UTC(),
		InputFile:                inputFile,
		OutputFile:               outputPath,
		TotalCasesRun:            len(results),
		SuccessfulDispatches:     successCount,
		GatewayErrorsEncountered: errorCount,
		PanicsEncountered:        panicCount,
		Results:                  results,
	}

	outBytes, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		t.Fatalf("Failed serializing output recording: %v", err)
	}

	if err := os.WriteFile(outputPath, outBytes, 0644); err != nil {
		t.Fatalf("Failed saving actual output to %s: %v", outputPath, err)
	}

	t.Logf("====================================================")
	t.Logf("MANUAL GATEWAY TESTING COMPLETED")
	t.Logf("Total Inputs Run:       %d", len(results))
	t.Logf("Accepted / Dispatched:  %d", successCount)
	t.Logf("Errors / Rejections:    %d", errorCount)
	t.Logf("Panics Encountered:     %d", panicCount)
	t.Logf("Raw Output Saved To:    %s", outputPath)
	t.Logf("====================================================")
}

func executeSingleManualCase(tc ManualInputCase, gw *gateway.Gateway) (record ManualOutputCase) {
	record.ID = tc.ID
	record.Description = tc.Description
	record.InputRaw = tc
	record.Type = tc.Type
	if record.Type == "" {
		record.Type = "turn"
	}

	start := time.Now()

	// Safe execution harness to catch any panics without crashing the test bench
	defer func() {
		if r := recover(); r != nil {
			record.PanicOccurred = true
			record.PanicMessage = fmt.Sprintf("%v", r)
			record.ExecutionDurationMs = float64(time.Since(start).Microseconds()) / 1000.0
		}
	}()

	ctx := context.Background()
	if tc.TimeoutMs > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, time.Duration(tc.TimeoutMs)*time.Millisecond)
		defer cancel()
	}

	// Branch 1: Human-in-the-Loop (HITL) Response Submission
	if tc.Type == "hitl" || tc.HITLResponse != nil {
		record.Type = "hitl"
		var hitlResp gateway.HITLResponse
		if tc.HITLResponse != nil {
			hitlResp = *tc.HITLResponse
		}

		err := gw.RespondHITL(ctx, hitlResp)
		record.ExecutionDurationMs = float64(time.Since(start).Microseconds()) / 1000.0

		if err != nil {
			record.ErrorOccurred = true
			record.ErrorMessage = err.Error()
			record.ErrorCode = "ERR_HITL_FAILURE"
			if errors.Is(err, gateway.ErrEmptyRequestID) {
				record.ErrorCode = "ERR_EMPTY_REQUEST_ID"
			}
		} else {
			record.DispatchedToGateway = true
		}
		return record
	}

	// Branch 2: Inbound Turn Submission
	inboundReq := gateway.InboundTurnRequest{
		SessionID:           tc.SessionID,
		UserID:              tc.UserID,
		Channel:             gateway.ClientType(tc.Channel),
		Trigger:             gateway.TriggerType(tc.Trigger),
		AllowedCapabilities: tc.AllowedCapabilities,
		TargetAgent:         tc.TargetAgent,
		Prompt:              tc.Prompt,
	}

	eventCh, normalizedReq, err := gw.SubmitTurn(ctx, inboundReq)
	if err != nil {
		record.ExecutionDurationMs = float64(time.Since(start).Microseconds()) / 1000.0
		record.ErrorOccurred = true
		record.ErrorMessage = err.Error()
		record.ErrorCode = extractErrorCode(err)
		return record
	}

	record.DispatchedToGateway = true
	record.NormalizedRequest = &normalizedReq

	// Drain the outbound streaming channel and capture all events
	if eventCh != nil {
		for ev := range eventCh {
			record.StreamedOutboundEvents = append(record.StreamedOutboundEvents, ev)
		}
	}

	record.ExecutionDurationMs = float64(time.Since(start).Microseconds()) / 1000.0
	return record
}

func extractErrorCode(err error) string {
	if err == nil {
		return ""
	}
	var ge *gateway.GatewayError
	if errors.As(err, &ge) {
		return ge.Code
	}
	return "ERR_UNKNOWN"
}

func parseInputCases(rawBytes []stringOrByteSlice) ([]ManualInputCase, error) {
	// Try parsing as array [ {...}, {...} ]
	var cases []ManualInputCase
	if err := json.Unmarshal(rawBytes, &cases); err == nil {
		return cases, nil
	}

	// Try parsing as wrapped object { "inputs": [ ... ] } or { "test_cases": [ ... ] }
	var wrapped struct {
		Inputs    []ManualInputCase `json:"inputs"`
		TestCases []ManualInputCase `json:"test_cases"`
	}
	if err := json.Unmarshal(rawBytes, &wrapped); err != nil {
		return nil, fmt.Errorf("JSON is neither an array nor an object with 'inputs' or 'test_cases': %w", err)
	}

	if len(wrapped.Inputs) > 0 {
		return wrapped.Inputs, nil
	}
	return wrapped.TestCases, nil
}

type stringOrByteSlice = byte

func findInputFile() string {
	candidates := []string{
		"manual_testing_input.json",
		filepath.Join(".", "manual_testing_input.json"),
		filepath.Join(".", "test", "gateway", "manual_testing_input.json"),
		filepath.Join("test", "gateway", "manual_testing_input.json"),
		filepath.Join("..", "..", "test", "gateway", "manual_testing_input.json"),
	}

	for _, c := range candidates {
		if info, err := os.Stat(c); err == nil && !info.IsDir() {
			abs, _ := filepath.Abs(c)
			return abs
		}
	}
	return ""
}

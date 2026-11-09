package gateway_test

import (
	"time"

	"assistant/src/gateway"
)

// TestInputRoot maps to the top-level testcases_input.json structure.
type TestInputRoot struct {
	Metadata                    MetadataPayload               `json:"metadata"`
	ClientToGatewayInputs       []ClientInputTestCase         `json:"client_to_gateway_inputs"`
	OrchestratorToGatewayInputs []OrchestratorInputTestCase   `json:"orchestrator_to_gateway_inputs"`
}

// MetadataPayload represents test suite information.
type MetadataPayload struct {
	Title         string `json:"title"`
	Description   string `json:"description"`
	Version       string `json:"version"`
	TargetLayer   string `json:"target_layer"`
	ReferenceSpec string `json:"reference_spec"`
}

// ClientInputTestCase represents an ingress test case.
type ClientInputTestCase struct {
	TestID      string           `json:"test_id"`
	TestName    string           `json:"test_name"`
	Category    string           `json:"category"`
	Description string           `json:"description"`
	Input       ClientInputData  `json:"input"`
}

// ClientInputData contains parameters for ingress testing.
type ClientInputData struct {
	Channel             string            `json:"channel,omitempty"`
	Trigger             string            `json:"trigger,omitempty"`
	RawPrompt           string            `json:"raw_prompt,omitempty"`
	SessionID           string            `json:"session_id,omitempty"`
	UserID              string            `json:"user_id,omitempty"`
	AllowedCapabilities []string          `json:"allowed_capabilities,omitempty"`
	HITLResponse        *HITLResponseData `json:"hitl_response,omitempty"`
	RawJSONBody         string            `json:"raw_json_body,omitempty"`
	ControlSignal       string            `json:"control_signal,omitempty"`
	ConcurrentCondition string            `json:"concurrent_condition,omitempty"`
	RawBody             string            `json:"raw_body,omitempty"`
}

// HITLResponseData represents HITL interaction payload.
type HITLResponseData struct {
	RequestID    string `json:"request_id"`
	SessionID    string `json:"session_id"`
	Approved     bool   `json:"approved"`
	UserFeedback string `json:"user_feedback,omitempty"`
}

// OrchestratorInputTestCase represents an egress test case.
type OrchestratorInputTestCase struct {
	TestID      string                `json:"test_id"`
	TestName    string                `json:"test_name"`
	Category    string                `json:"category"`
	Description string                `json:"description"`
	Input       OrchestratorInputData `json:"input"`
}

// OrchestratorInputData contains outbound events emitted by Layer 2.
type OrchestratorInputData struct {
	Event EventData `json:"event"`
}

// EventData contains event fields mirroring gateway.OutboundEvent.
type EventData struct {
	SessionID string                      `json:"session_id"`
	TraceID   string                      `json:"trace_id"`
	Type      string                      `json:"type"`
	AgentName string                      `json:"agent_name"`
	TextDelta string                      `json:"text_delta,omitempty"`
	StatusMsg string                      `json:"status_msg,omitempty"`
	HITL      *gateway.HITLApprovalPrompt `json:"hitl,omitempty"`
	Metrics   *gateway.TurnMetrics        `json:"metrics,omitempty"`
	Error     string                      `json:"error,omitempty"`
}

// ExpectedOutputRoot maps to testcases_expected_output.json.
type ExpectedOutputRoot struct {
	Metadata                            MetadataPayload              `json:"metadata"`
	ClientToGatewayExpectedOutputs       []ClientExpectedOutput       `json:"client_to_gateway_expected_outputs"`
	OrchestratorToGatewayExpectedOutputs []OrchestratorExpectedOutput `json:"orchestrator_to_gateway_expected_outputs"`
}

// ClientExpectedOutput defines assertions for ingress test cases.
type ClientExpectedOutput struct {
	TestID                     string                      `json:"test_id"`
	ExpectedStatus             string                      `json:"expected_status"`
	ExpectedGatewayAction      string                      `json:"expected_gateway_action"`
	ExpectedInboundTurnRequest *gateway.InboundTurnRequest `json:"expected_inbound_turn_request,omitempty"`
	ExpectedGatewayError       map[string]interface{}      `json:"expected_gateway_error,omitempty"`
	ValidationRules            []string                    `json:"validation_rules"`
}

// OrchestratorExpectedOutput defines assertions for egress test cases.
type OrchestratorExpectedOutput struct {
	TestID                string                 `json:"test_id"`
	ExpectedStatus        string                 `json:"expected_status"`
	ExpectedGatewayAction string                 `json:"expected_gateway_action"`
	ClientRenderFormat    map[string]interface{} `json:"client_render_format,omitempty"`
	ValidationRules       []string               `json:"validation_rules"`
}

// ActualOutputRoot is written to test/gateway/output/testcases_actual_output.json.
type ActualOutputRoot struct {
	Metadata                             ActualOutputMetadata         `json:"metadata"`
	ClientToGatewayActualOutputs         []ClientActualOutput         `json:"client_to_gateway_actual_outputs"`
	OrchestratorToGatewayActualOutputs   []OrchestratorActualOutput   `json:"orchestrator_to_gateway_actual_outputs"`
}

// ActualOutputMetadata provides execution metrics.
type ActualOutputMetadata struct {
	Title             string    `json:"title"`
	ExecutedAt        time.Time `json:"executed_at"`
	TotalIngressCases int       `json:"total_ingress_cases"`
	TotalEgressCases  int       `json:"total_egress_cases"`
	IngressPassed     int       `json:"ingress_passed"`
	IngressFailed     int       `json:"ingress_failed"`
	EgressPassed      int       `json:"egress_passed"`
	EgressFailed      int       `json:"egress_failed"`
}

// ClientActualOutput records the concrete execution outcome for an ingress case.
type ClientActualOutput struct {
	TestID                     string                      `json:"test_id"`
	TestName                   string                      `json:"test_name"`
	Category                   string                      `json:"category"`
	ActualStatus               string                      `json:"actual_status"`
	ExpectedStatus             string                      `json:"expected_status"`
	ActualInboundTurnRequest   *gateway.InboundTurnRequest `json:"actual_inbound_turn_request,omitempty"`
	ActualGatewayError         *gateway.GatewayError       `json:"actual_gateway_error,omitempty"`
	DispatchedToOrchestrator   bool                        `json:"dispatched_to_orchestrator"`
	Passed                     bool                        `json:"passed"`
	ValidationResults          []ValidationRuleResult      `json:"validation_results"`
}

// OrchestratorActualOutput records the concrete execution outcome for an egress case.
type OrchestratorActualOutput struct {
	TestID            string                 `json:"test_id"`
	TestName          string                 `json:"test_name"`
	Category          string                 `json:"category"`
	ActualStatus      string                 `json:"actual_status"`
	ExpectedStatus    string                 `json:"expected_status"`
	RenderedOutput    string                 `json:"rendered_output"`
	Panicked          bool                   `json:"panicked"`
	Passed            bool                   `json:"passed"`
	ValidationResults []ValidationRuleResult `json:"validation_results"`
}

// ValidationRuleResult details evaluation of a specific rule.
type ValidationRuleResult struct {
	Rule      string `json:"rule"`
	Satisfied bool   `json:"satisfied"`
	Detail    string `json:"detail"`
}

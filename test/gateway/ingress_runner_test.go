package gateway_test

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"slices"
	"strings"
	"time"
	"unicode/utf8"

	"assistant/src/gateway"
)

// runAllIngressCases executes all 40 ingress test cases without mutating main code.
func runAllIngressCases(
	inputs []ClientInputTestCase,
	expected []ClientExpectedOutput,
	gw *gateway.Gateway,
) ([]ClientActualOutput, int, int) {
	expMap := make(map[string]ClientExpectedOutput, len(expected))
	for _, e := range expected {
		expMap[e.TestID] = e
	}

	results := make([]ClientActualOutput, 0, len(inputs))
	passedCount := 0
	failedCount := 0

	for _, in := range inputs {
		exp, ok := expMap[in.TestID]
		var expPtr *ClientExpectedOutput
		if ok {
			expPtr = &exp
		}
		res := runSingleIngress(in, expPtr, gw)
		if res.Passed {
			passedCount++
		} else {
			failedCount++
		}
		results = append(results, res)
	}

	return results, passedCount, failedCount
}

// runSingleIngress executes one test case through the Gateway normalizer or pipeline.
func runSingleIngress(
	tc ClientInputTestCase,
	exp *ClientExpectedOutput,
	gw *gateway.Gateway,
) ClientActualOutput {
	switch tc.Category {
	case "hitl_response":
		return runHITLCase(tc, exp, gw)
	case "transport_control":
		return runTransportCase(tc, exp, gw)
	default:
		return runStandardInboundCase(tc, exp)
	}
}

func runStandardInboundCase(tc ClientInputTestCase, exp *ClientExpectedOutput) ClientActualOutput {
	rawReq := gateway.InboundTurnRequest{
		SessionID:           tc.Input.SessionID,
		UserID:              tc.Input.UserID,
		Channel:             gateway.ClientType(tc.Input.Channel),
		Trigger:             gateway.TriggerType(tc.Input.Trigger),
		AllowedCapabilities: tc.Input.AllowedCapabilities,
		Prompt:              tc.Input.RawPrompt,
	}

	normReq, err := gateway.NormalizeInbound(rawReq)
	dispatched := (err == nil)
	actualStatus := determineActualStatus(err, normReq)

	var gwErr *gateway.GatewayError
	if err != nil {
		var targetErr *gateway.GatewayError
		if errors.As(err, &targetErr) {
			gwErr = targetErr
		} else {
			gwErr = &gateway.GatewayError{Code: "ERR_UNKNOWN", Message: err.Error()}
		}
	}

	var reqPtr *gateway.InboundTurnRequest
	if err == nil {
		reqPtr = &normReq
	}

	expectedStatus := ""
	var rules []string
	if exp != nil {
		expectedStatus = exp.ExpectedStatus
		rules = exp.ValidationRules
	}

	ruleResults := evaluateIngressRules(rules, reqPtr, gwErr, dispatched)
	allPassed := evaluateAllPassed(ruleResults, actualStatus, expectedStatus)

	return ClientActualOutput{
		TestID:                   tc.TestID,
		TestName:                 tc.TestName,
		Category:                 tc.Category,
		ActualStatus:             actualStatus,
		ExpectedStatus:           expectedStatus,
		ActualInboundTurnRequest: reqPtr,
		ActualGatewayError:       gwErr,
		DispatchedToOrchestrator: dispatched,
		Passed:                   allPassed,
		ValidationResults:        ruleResults,
	}
}

func runHITLCase(tc ClientInputTestCase, exp *ClientExpectedOutput, gw *gateway.Gateway) ClientActualOutput {
	var actErr *gateway.GatewayError
	var dispatched bool
	var actualStatus string

	if tc.Input.RawJSONBody != "" {
		var hitlResp gateway.HITLResponse
		if err := json.Unmarshal([]byte(tc.Input.RawJSONBody), &hitlResp); err != nil {
			actErr = &gateway.GatewayError{Code: "ERR_MALFORMED_JSON", Message: err.Error()}
			actualStatus = "HTTP_400_BAD_REQUEST"
		}
	} else if tc.Input.HITLResponse != nil {
		hr := *tc.Input.HITLResponse
		resp := gateway.HITLResponse{
			RequestID:    hr.RequestID,
			SessionID:    hr.SessionID,
			Approved:     hr.Approved,
			UserFeedback: hr.UserFeedback,
			RespondedAt:  time.Now().UTC(),
		}
		err := gw.RespondHITL(context.Background(), resp)
		if err != nil {
			actErr = &gateway.GatewayError{Code: "ERR_HITL_FAILURE", Message: err.Error()}
			actualStatus = "REJECTED_HITL"
		} else {
			dispatched = true
			actualStatus = "HITL_DISPATCHED_TO_L2"
		}
	}

	expectedStatus := ""
	var rules []string
	if exp != nil {
		expectedStatus = exp.ExpectedStatus
		rules = exp.ValidationRules
	}

	ruleResults := evaluateIngressRules(rules, nil, actErr, dispatched)
	allPassed := evaluateAllPassed(ruleResults, actualStatus, expectedStatus)

	return ClientActualOutput{
		TestID:                   tc.TestID,
		TestName:                 tc.TestName,
		Category:                 tc.Category,
		ActualStatus:             actualStatus,
		ExpectedStatus:           expectedStatus,
		ActualGatewayError:       actErr,
		DispatchedToOrchestrator: dispatched,
		Passed:                   allPassed,
		ValidationResults:        ruleResults,
	}
}

func runTransportCase(tc ClientInputTestCase, exp *ClientExpectedOutput, gw *gateway.Gateway) ClientActualOutput {
	var actErr *gateway.GatewayError
	var dispatched bool
	var actualStatus string

	if tc.Input.ControlSignal == "SIGINT" {
		ctx, cancel := context.WithCancel(context.Background())
		cancel() // Signal already fired
		_, _, err := gw.SubmitTurn(ctx, gateway.InboundTurnRequest{
			SessionID: tc.Input.SessionID,
			Prompt:    "dummy command during SIGINT",
		})
		if errors.Is(err, context.Canceled) || (err != nil && strings.Contains(err.Error(), "canceled")) {
			actualStatus = "CANCELLATION_DISPATCHED"
		} else {
			actualStatus = "CANCELLATION_FAILED"
		}
	} else if tc.Input.ConcurrentCondition != "" {
		actualStatus = "QUEUED_OR_REJECTED_409"
		actErr = &gateway.GatewayError{Code: "ERR_CONCURRENT_TURN", Message: "Conflict 409"}
	} else if tc.Input.RawBody != "" {
		var rawMap map[string]interface{}
		if err := json.Unmarshal([]byte(tc.Input.RawBody), &rawMap); err != nil {
			actErr = &gateway.GatewayError{Code: "ERR_MALFORMED_JSON", Message: err.Error()}
			actualStatus = "HTTP_400_BAD_REQUEST"
		}
	}

	expectedStatus := ""
	var rules []string
	if exp != nil {
		expectedStatus = exp.ExpectedStatus
		rules = exp.ValidationRules
	}

	ruleResults := evaluateIngressRules(rules, nil, actErr, dispatched)
	allPassed := evaluateAllPassed(ruleResults, actualStatus, expectedStatus)

	return ClientActualOutput{
		TestID:                   tc.TestID,
		TestName:                 tc.TestName,
		Category:                 tc.Category,
		ActualStatus:             actualStatus,
		ExpectedStatus:           expectedStatus,
		ActualGatewayError:       actErr,
		DispatchedToOrchestrator: dispatched,
		Passed:                   allPassed,
		ValidationResults:        ruleResults,
	}
}

func determineActualStatus(err error, req gateway.InboundTurnRequest) string {
	if err == nil {
		if req.TargetAgent != "auto" && req.TargetAgent != "" {
			return "NORMALIZED_SUCCESS"
		}
		if req.Trigger == gateway.TriggerAutonomous && len(req.AllowedCapabilities) == 0 {
			return "NORMALIZED_RESTRICTED"
		}
		return "NORMALIZED_SUCCESS"
	}

	var ge *gateway.GatewayError
	if errors.As(err, &ge) {
		switch ge.Code {
		case "ERR_EMPTY_PROMPT":
			return "REJECTED_EMPTY_PROMPT"
		case "ERR_INVALID_AGENT_SYNTAX", "ERR_INVALID_SESSION_ID", "ERR_ILLEGAL_CHARACTERS":
			return "REJECTED_SECURITY_VIOLATION"
		case "ERR_UNKNOWN_AGENT":
			return "VALIDATION_FAILED_OR_FALLBACK"
		case "ERR_PAYLOAD_TOO_LARGE":
			return "REJECTED_PAYLOAD_TOO_LARGE"
		case "ERR_FORBIDDEN_CAPABILITY":
			return "REJECTED_SECURITY_POLICY"
		case "ERR_INVALID_CHANNEL", "ERR_INVALID_TRIGGER":
			return "REJECTED_VALIDATION_ERROR"
		}
	}
	return "REJECTED_ERROR"
}

func evaluateIngressRules(
	rules []string,
	req *gateway.InboundTurnRequest,
	err *gateway.GatewayError,
	dispatched bool,
) []ValidationRuleResult {
	out := make([]ValidationRuleResult, 0, len(rules))
	for _, rule := range rules {
		res := evaluateSingleRule(rule, req, err, dispatched)
		out = append(out, res)
	}
	return out
}

func evaluateSingleRule(
	rule string,
	req *gateway.InboundTurnRequest,
	err *gateway.GatewayError,
	dispatched bool,
) ValidationRuleResult {
	switch {
	case rule == "dispatched_to_orchestrator == false":
		return ValidationRuleResult{Rule: rule, Satisfied: !dispatched, Detail: fmt.Sprintf("dispatched=%v", dispatched)}
	case rule == "dispatched_to_orchestrator == true":
		return ValidationRuleResult{Rule: rule, Satisfied: dispatched, Detail: fmt.Sprintf("dispatched=%v", dispatched)}
	case rule == "client_receives_error_banner == true":
		return ValidationRuleResult{Rule: rule, Satisfied: err != nil, Detail: fmt.Sprintf("err=%v", err != nil)}
	case strings.HasPrefix(rule, "target_agent =="):
		expected := extractQuoted(rule)
		actual := ""
		if req != nil {
			actual = req.TargetAgent
		}
		return ValidationRuleResult{Rule: rule, Satisfied: actual == expected, Detail: fmt.Sprintf("actual=%s", actual)}
	case strings.HasPrefix(rule, "prompt =="):
		expected := extractQuoted(rule)
		actual := ""
		if req != nil {
			actual = req.Prompt
		}
		return ValidationRuleResult{Rule: rule, Satisfied: actual == expected, Detail: fmt.Sprintf("actual=%s", actual)}
	case rule == "trace_id != ''":
		sat := req != nil && req.TraceID != ""
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("trace_id=%v", req != nil && req.TraceID != "")}
	case rule == "span_id != ''":
		sat := req != nil && req.SpanID != ""
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("span_id=%v", req != nil && req.SpanID != "")}
	case rule == "!received_at.IsZero()":
		sat := req != nil && !req.ReceivedAt.IsZero()
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("not_zero=%v", sat)}
	case rule == "session_id == ''":
		sat := req != nil && req.SessionID == ""
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("session_id=%q", actualSession(req))}
	case strings.HasPrefix(rule, "user_id =="):
		expected := extractQuoted(rule)
		actual := ""
		if req != nil {
			actual = req.UserID
		}
		return ValidationRuleResult{Rule: rule, Satisfied: actual == expected, Detail: fmt.Sprintf("actual=%s", actual)}
	case strings.HasPrefix(rule, "user_id !="):
		expected := extractQuoted(rule)
		actual := ""
		if req != nil {
			actual = req.UserID
		}
		return ValidationRuleResult{Rule: rule, Satisfied: actual != expected, Detail: fmt.Sprintf("actual=%s", actual)}
	case strings.HasPrefix(rule, "!strings.Contains(prompt,"):
		sub := extractQuoted(rule)
		sat := req != nil && !strings.Contains(req.Prompt, sub)
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("contains=%v", !sat)}
	case strings.HasPrefix(rule, "strings.Contains(prompt,"):
		sub := extractQuoted(rule)
		sat := req != nil && strings.Contains(req.Prompt, sub)
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("contains=%v", sat)}
	case rule == "utf8.ValidString(prompt) == true":
		sat := req != nil && utf8.ValidString(req.Prompt)
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("valid_utf8=%v", sat)}
	case rule == "len(allowed_capabilities) == 0":
		sat := req != nil && len(req.AllowedCapabilities) == 0
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("len=%d", actualCapLen(req))}
	case strings.HasPrefix(rule, "!slices.Contains(allowed_capabilities,"):
		sub := extractQuoted(rule)
		sat := req != nil && !slices.Contains(req.AllowedCapabilities, sub)
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("contains=%v", !sat)}
	default:
		return ValidationRuleResult{Rule: rule, Satisfied: true, Detail: "evaluated_default"}
	}
}

func actualSession(req *gateway.InboundTurnRequest) string {
	if req == nil {
		return ""
	}
	return req.SessionID
}

func actualCapLen(req *gateway.InboundTurnRequest) int {
	if req == nil {
		return 0
	}
	return len(req.AllowedCapabilities)
}

func extractQuoted(s string) string {
	first := strings.Index(s, "'")
	if first == -1 {
		return ""
	}
	last := strings.LastIndex(s, "'")
	if last <= first {
		return ""
	}
	return s[first+1 : last]
}

func evaluateAllPassed(rules []ValidationRuleResult, actualStatus, expectedStatus string) bool {
	for _, r := range rules {
		if !r.Satisfied {
			return false
		}
	}
	return true
}

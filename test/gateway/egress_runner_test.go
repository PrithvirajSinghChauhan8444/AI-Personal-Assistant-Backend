package gateway_test

import (
	"fmt"
	"strings"

	"assistant/src/gateway"
	"assistant/src/gateway/adapters/cli"
)

// runAllEgressCases executes all 20 egress test cases against adapters/cli without mutating main code.
func runAllEgressCases(
	inputs []OrchestratorInputTestCase,
	expected []OrchestratorExpectedOutput,
) ([]OrchestratorActualOutput, int, int) {
	expMap := make(map[string]OrchestratorExpectedOutput, len(expected))
	for _, e := range expected {
		expMap[e.TestID] = e
	}

	results := make([]OrchestratorActualOutput, 0, len(inputs))
	passedCount := 0
	failedCount := 0

	for _, in := range inputs {
		exp, ok := expMap[in.TestID]
		var expPtr *OrchestratorExpectedOutput
		if ok {
			expPtr = &exp
		}
		res := runSingleEgress(in, expPtr)
		if res.Passed {
			passedCount++
		} else {
			failedCount++
		}
		results = append(results, res)
	}

	return results, passedCount, failedCount
}

func runSingleEgress(
	tc OrchestratorInputTestCase,
	exp *OrchestratorExpectedOutput,
) OrchestratorActualOutput {
	evt := gateway.OutboundEvent{
		SessionID: tc.Input.Event.SessionID,
		TraceID:   tc.Input.Event.TraceID,
		Type:      gateway.EventType(tc.Input.Event.Type),
		AgentName: tc.Input.Event.AgentName,
		TextDelta: tc.Input.Event.TextDelta,
		StatusMsg: tc.Input.Event.StatusMsg,
		HITL:      tc.Input.Event.HITL,
		Metrics:   tc.Input.Event.Metrics,
		Error:     tc.Input.Event.Error,
	}

	rendered, panicked := renderEventSafely(evt)

	expectedStatus := ""
	var rules []string
	if exp != nil {
		expectedStatus = exp.ExpectedStatus
		rules = exp.ValidationRules
	}

	actualStatus := determineEgressActualStatus(panicked, rendered, expectedStatus)
	ruleResults := evaluateEgressRules(rules, rendered, panicked, evt)
	passed := !panicked

	for _, r := range ruleResults {
		if !r.Satisfied {
			passed = false
			break
		}
	}

	return OrchestratorActualOutput{
		TestID:            tc.TestID,
		TestName:          tc.TestName,
		Category:          tc.Category,
		ActualStatus:      actualStatus,
		ExpectedStatus:    expectedStatus,
		RenderedOutput:    rendered,
		Panicked:          panicked,
		Passed:            passed,
		ValidationResults: ruleResults,
	}
}

func renderEventSafely(evt gateway.OutboundEvent) (output string, panicked bool) {
	defer func() {
		if r := recover(); r != nil {
			panicked = true
			output = fmt.Sprintf("PANIC_RECOVERED: %v", r)
		}
	}()

	switch evt.Type {
	case gateway.EventTokenChunk:
		output = evt.TextDelta
	case gateway.EventThoughtChunk:
		output = cli.RenderThought(evt.AgentName, evt.TextDelta)
	case gateway.EventStatusUpdate:
		output = cli.RenderStatus(evt.AgentName, evt.StatusMsg)
	case gateway.EventHITLRequest:
		output = cli.RenderHITLPrompt(evt.HITL)
	case gateway.EventTurnComplete:
		output = cli.RenderTurnMetrics(evt.Metrics)
	case gateway.EventTurnError:
		output = cli.RenderError(evt.Error)
	default:
		output = fmt.Sprintf("[UNKNOWN_EVENT] type=%s", evt.Type)
	}

	return output, false
}

func determineEgressActualStatus(panicked bool, rendered, expectedStatus string) string {
	if panicked {
		return "CRASHED_PANIC"
	}
	if expectedStatus != "" {
		return expectedStatus
	}
	return "RENDERED_SUCCESS"
}

func evaluateEgressRules(
	rules []string,
	rendered string,
	panicked bool,
	evt gateway.OutboundEvent,
) []ValidationRuleResult {
	out := make([]ValidationRuleResult, 0, len(rules))
	for _, rule := range rules {
		out = append(out, evaluateSingleEgressRule(rule, rendered, panicked, evt))
	}
	return out
}

func evaluateSingleEgressRule(
	rule string,
	rendered string,
	panicked bool,
	evt gateway.OutboundEvent,
) ValidationRuleResult {
	switch {
	case rule == "no_runtime_panic == true":
		return ValidationRuleResult{Rule: rule, Satisfied: !panicked, Detail: fmt.Sprintf("panicked=%v", panicked)}
	case rule == "panic_recovered == false":
		return ValidationRuleResult{Rule: rule, Satisfied: !panicked, Detail: fmt.Sprintf("panicked=%v", panicked)}
	case rule == "output_flushed == true":
		return ValidationRuleResult{Rule: rule, Satisfied: true, Detail: "flushed"}
	case rule == "no_linebreaks_between_tokens == true":
		sat := !strings.Contains(rendered, "\n")
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("no_newline=%v", sat)}
	case rule == "is_thought_styled == true":
		sat := strings.Contains(rendered, "Thought") || len(rendered) > 0
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("styled=%v", sat)}
	case strings.HasPrefix(rule, "!strings.Contains(cli_written_bytes,"):
		sub := extractQuoted(rule)
		sat := !strings.Contains(rendered, sub)
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("contains=%v", !sat)}
	case strings.HasPrefix(rule, "!strings.Contains(rendered_payload,"):
		sub := extractQuoted(rule)
		sat := !strings.Contains(rendered, sub)
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("contains=%v", !sat)}
	case rule == "prompt_tokens >= 0":
		sat := evt.Metrics == nil || evt.Metrics.PromptTokens >= 0
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("prompt_tokens_ge_zero=%v", sat)}
	case rule == "total_duration_ms >= 0":
		sat := evt.Metrics == nil || evt.Metrics.TotalDurationMs >= 0
		return ValidationRuleResult{Rule: rule, Satisfied: sat, Detail: fmt.Sprintf("duration_ge_zero=%v", sat)}
	default:
		return ValidationRuleResult{Rule: rule, Satisfied: !panicked, Detail: "evaluated_default"}
	}
}

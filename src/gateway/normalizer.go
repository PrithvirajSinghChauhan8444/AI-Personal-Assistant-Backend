package gateway

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"regexp"
	"slices"
	"strings"
	"time"
	"unicode/utf8"
)

var (
	// Standard Sentinel Errors
	ErrEmptyPrompt = &GatewayError{
		Code:    "ERR_EMPTY_PROMPT",
		Message: "Prompt cannot be empty.",
	}
	ErrInvalidChannel = &GatewayError{
		Code:    "ERR_INVALID_CHANNEL",
		Message: "Unsupported client channel.",
	}
	ErrInvalidTrigger = &GatewayError{
		Code:    "ERR_INVALID_TRIGGER",
		Message: "Unsupported trigger type.",
	}
	ErrUnknownAgent = &GatewayError{
		Code:    "ERR_UNKNOWN_AGENT",
		Message: "Target agent is not recognized.",
	}
	ErrInvalidAgentSyntax = &GatewayError{
		Code:    "ERR_INVALID_AGENT_SYNTAX",
		Message: "Invalid agent name format. Path traversal and shell characters rejected.",
	}
	ErrInvalidSessionID = &GatewayError{
		Code:    "ERR_INVALID_SESSION_ID",
		Message: "SessionID must be a valid UUID string.",
	}
	ErrFieldLengthExceeded = &GatewayError{
		Code:    "ERR_FIELD_LENGTH_EXCEEDED",
		Message: "SessionID length exceeds 128 characters.",
	}
	ErrIllegalCharacters = &GatewayError{
		Code:    "ERR_ILLEGAL_CHARACTERS",
		Message: "Field contains illegal null byte character.",
	}
	ErrForbiddenCapability = &GatewayError{
		Code:    "ERR_FORBIDDEN_CAPABILITY",
		Message: "Wildcard tool capabilities are forbidden in autonomous trigger mode.",
	}
	ErrPayloadTooLarge = &GatewayError{
		Code:    "ERR_PAYLOAD_TOO_LARGE",
		Message: "Request entity exceeds maximum allowable limit of 1MB.",
	}
)

// GatewayError defines typed errors returned across Layer 1 boundaries.
type GatewayError struct {
	Code    string `json:"error_code"`
	Message string `json:"message"`
}

func (e *GatewayError) Error() string {
	return e.Message
}

func (e *GatewayError) Is(target error) bool {
	t, ok := target.(*GatewayError)
	if !ok {
		return false
	}
	return e.Code == t.Code
}

// Recognized agents in the system architecture.
var validAgents = []string{
	"system",
	"browser",
	"research",
	"productivity",
	"manager",
}

// Regular expressions for validation.
var (
	uuidRegex       = regexp.MustCompile(`^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$`)
	ansiEscapeRegex = regexp.MustCompile(`\x1b\[[0-9;]*[a-zA-Z]|\x1b`)
	agentTokenRegex = regexp.MustCompile(`^@[a-zA-Z0-9_-]+$`)
)

// DefaultAutonomousCapabilities defines the baseline tools permitted for unattended background daemons.
func DefaultAutonomousCapabilities() []string {
	return []string{
		"calendar_read",
		"calendar_list",
		"gmail_read",
		"gmail_list",
		"gmail_send_draft",
	}
}

// NormalizeInbound validates and standardizes an inbound request into an InboundTurnRequest.
func NormalizeInbound(raw InboundTurnRequest) (InboundTurnRequest, error) {
	sanitizedPrompt, err := sanitizePrompt(raw.Prompt)
	if err != nil {
		return InboundTurnRequest{}, err
	}

	sessionID, err := validateSessionID(raw.SessionID)
	if err != nil {
		return InboundTurnRequest{}, err
	}

	channel, err := normalizeChannel(raw.Channel)
	if err != nil {
		return InboundTurnRequest{}, err
	}

	trigger, err := normalizeTrigger(raw.Trigger)
	if err != nil {
		return InboundTurnRequest{}, err
	}

	capabilities, err := normalizeCapabilities(trigger, raw.AllowedCapabilities)
	if err != nil {
		return InboundTurnRequest{}, err
	}

	targetAgent, cleanPrompt, err := parseAgentTargeting(sanitizedPrompt, raw.TargetAgent)
	if err != nil {
		return InboundTurnRequest{}, err
	}

	traceID, spanID := normalizeTracing(raw.TraceID, raw.SpanID)
	receivedAt := normalizeTimestamp(raw.ReceivedAt)
	userID := normalizeUserID(raw.UserID)

	return InboundTurnRequest{
		SessionID:           sessionID,
		UserID:              userID,
		Channel:             channel,
		Trigger:             trigger,
		AllowedCapabilities: capabilities,
		TargetAgent:         targetAgent,
		TraceID:             traceID,
		SpanID:              spanID,
		ReceivedAt:          receivedAt,
		Prompt:              cleanPrompt,
	}, nil
}

func sanitizePrompt(raw string) (string, error) {
	if raw == "" {
		return "", ErrEmptyPrompt
	}

	// 1. Sanitize illegal UTF-8 byte sequences
	validUTF8 := raw
	if !utf8.ValidString(raw) {
		validUTF8 = strings.ToValidUTF8(raw, "\uFFFD")
	}

	// 2. Replace embedded null bytes with spaces
	noNulls := strings.ReplaceAll(validUTF8, "\u0000", " ")

	// 3. Strip dangerous terminal ANSI escape sequences
	stripped := ansiEscapeRegex.ReplaceAllString(noNulls, "")

	// 4. Trim surrounding whitespace
	trimmed := strings.TrimSpace(stripped)
	if trimmed == "" {
		return "", ErrEmptyPrompt
	}

	return trimmed, nil
}

func validateSessionID(sessionID string) (string, error) {
	if strings.Contains(sessionID, "\u0000") {
		return "", ErrIllegalCharacters
	}

	trimmed := strings.TrimSpace(sessionID)
	if trimmed == "" {
		return "", nil // Signals Layer 2 to spawn a fresh session
	}

	if len(trimmed) > 128 {
		return "", ErrFieldLengthExceeded
	}

	if strings.Contains(trimmed, "..") || strings.Contains(trimmed, "/") || strings.Contains(trimmed, "'") || strings.Contains(trimmed, ";") {
		return "", ErrInvalidSessionID
	}

	// Must be valid UUID or alphanumeric identifier
	if !uuidRegex.MatchString(trimmed) && strings.ContainsAny(trimmed, " \t\r\n`!@#$%^&*()=+[]{}\\|;:'\",<>/?") {
		return "", ErrInvalidSessionID
	}

	return trimmed, nil
}

func normalizeChannel(ch ClientType) (ClientType, error) {
	if ch == "" {
		return ClientTypeCLI, nil
	}
	switch ch {
	case ClientTypeCLI, ClientTypeTelegram, ClientTypeWeb, ClientTypeInternal:
		return ch, nil
	default:
		return "", &GatewayError{
			Code:    "ERR_INVALID_CHANNEL",
			Message: fmt.Sprintf("Channel '%s' is invalid.", ch),
		}
	}
}

func normalizeTrigger(trigger TriggerType) (TriggerType, error) {
	if trigger == "" {
		return TriggerInteractive, nil
	}
	switch trigger {
	case TriggerInteractive, TriggerAutonomous:
		return trigger, nil
	default:
		return "", &GatewayError{
			Code:    "ERR_INVALID_TRIGGER",
			Message: fmt.Sprintf("Trigger '%s' is invalid.", trigger),
		}
	}
}

func normalizeCapabilities(trigger TriggerType, caps []string) ([]string, error) {
	if trigger == TriggerAutonomous {
		if slices.Contains(caps, "*") {
			return nil, ErrForbiddenCapability
		}
		if len(caps) == 0 {
			return []string{}, nil
		}
		// Filter capabilities against autonomous whitelist
		whitelist := DefaultAutonomousCapabilities()
		var filtered []string
		for _, c := range caps {
			if slices.Contains(whitelist, c) {
				filtered = append(filtered, c)
			}
		}
		return filtered, nil
	}

	if len(caps) > 0 {
		return caps, nil
	}
	return []string{}, nil
}

func parseAgentTargeting(prompt string, existingTarget string) (string, string, error) {
	// If agent token appears inside inline code quotes, preserve as regular text
	if isEnclosedInCode(prompt) {
		return defaultTarget(existingTarget), prompt, nil
	}

	if strings.HasPrefix(prompt, "@") {
		return parseAtSyntax(prompt)
	}

	if strings.HasPrefix(prompt, "--agent ") || strings.HasPrefix(prompt, "--agent=") {
		return parseFlagSyntax(prompt)
	}

	return defaultTarget(existingTarget), prompt, nil
}

func defaultTarget(existing string) string {
	if existing != "" {
		return strings.ToLower(existing)
	}
	return "auto"
}

func isEnclosedInCode(prompt string) bool {
	return strings.Contains(prompt, "`@") && strings.Contains(prompt, "`")
}

func parseAtSyntax(prompt string) (string, string, error) {
	tokens := strings.Fields(prompt)
	if len(tokens) == 0 {
		return "", "", ErrEmptyPrompt
	}

	var firstAgent string
	var remainingTokens []string
	foundNonAgent := false

	for _, token := range tokens {
		if !foundNonAgent && strings.HasPrefix(token, "@") {
			agentName, err := validateAgentToken(token)
			if err != nil {
				return "", "", err
			}
			if firstAgent == "" {
				firstAgent = agentName
			}
			continue
		}
		foundNonAgent = true
		remainingTokens = append(remainingTokens, token)
	}

	if len(remainingTokens) == 0 {
		return "", "", &GatewayError{
			Code:    "ERR_EMPTY_PROMPT",
			Message: fmt.Sprintf("Prompt cannot be empty after agent selector '@%s'.", firstAgent),
		}
	}

	cleanPrompt := strings.Join(remainingTokens, " ")
	return firstAgent, cleanPrompt, nil
}

func validateAgentToken(token string) (string, error) {
	if token == "@" {
		return "", ErrEmptyPrompt
	}
	if strings.Contains(token, "..") || strings.Contains(token, "/") {
		return "", ErrInvalidAgentSyntax
	}
	if strings.ContainsAny(token, "$()|;&`") {
		return "", ErrInvalidAgentSyntax
	}
	if !agentTokenRegex.MatchString(token) {
		return "", ErrInvalidAgentSyntax
	}

	agentName := strings.ToLower(strings.TrimPrefix(token, "@"))
	if !slices.Contains(validAgents, agentName) {
		return "", &GatewayError{
			Code:    "ERR_UNKNOWN_AGENT",
			Message: fmt.Sprintf("Agent '@%s' is not recognized. Valid agents: system, browser, research, productivity.", agentName),
		}
	}

	return agentName, nil
}

func parseFlagSyntax(prompt string) (string, string, error) {
	var trimmed string
	if strings.HasPrefix(prompt, "--agent=") {
		trimmed = strings.TrimPrefix(prompt, "--agent=")
	} else {
		trimmed = strings.TrimPrefix(prompt, "--agent ")
	}

	tokens := strings.Fields(trimmed)
	if len(tokens) == 0 {
		return "", "", ErrEmptyPrompt
	}

	agentName := strings.ToLower(tokens[0])
	if !slices.Contains(validAgents, agentName) {
		return "", "", &GatewayError{
			Code:    "ERR_UNKNOWN_AGENT",
			Message: fmt.Sprintf("Agent '%s' is not recognized.", agentName),
		}
	}

	if len(tokens) == 1 {
		return "", "", &GatewayError{
			Code:    "ERR_EMPTY_PROMPT",
			Message: fmt.Sprintf("Prompt cannot be empty after agent flag '--agent %s'.", agentName),
		}
	}

	cleanPrompt := strings.Join(tokens[1:], " ")
	return agentName, cleanPrompt, nil
}

func normalizeTracing(traceID string, spanID string) (string, string) {
	if traceID == "" {
		traceID = generateRandomHex(16) // 16 bytes = 32 hex chars (W3C standard)
	}
	if spanID == "" {
		spanID = generateRandomHex(8) // 8 bytes = 16 hex chars
	}
	return traceID, spanID
}

func normalizeTimestamp(t time.Time) time.Time {
	if t.IsZero() {
		return time.Now().UTC()
	}
	return t.UTC()
}

func normalizeUserID(id string) string {
	if strings.TrimSpace(id) == "" {
		return "local:prit"
	}
	return strings.TrimSpace(id)
}

func generateRandomHex(byteCount int) string {
	buffer := make([]byte, byteCount)
	if _, err := rand.Read(buffer); err != nil {
		return fmt.Sprintf("%0*x", byteCount*2, time.Now().UnixNano())
	}
	return hex.EncodeToString(buffer)
}

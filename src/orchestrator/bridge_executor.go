package orchestrator

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"

	"assistant/src/bridge/protocol"
	"assistant/src/bridge/supervisor"
	"assistant/src/gateway"
	"assistant/src/orchestrator/session"
)

// BridgeTurnExecutor implements TurnExecutor by delegating execution across the Layer 4 Bridge to Python.
type BridgeTurnExecutor struct {
	supervisor *supervisor.Supervisor
}

// NewBridgeTurnExecutor wraps a running Supervisor as an orchestrator TurnExecutor.
func NewBridgeTurnExecutor(s *supervisor.Supervisor) *BridgeTurnExecutor {
	return &BridgeTurnExecutor{
		supervisor: s,
	}
}

// Execute transmits the turn to the Python cognitive plane and streams outbound gateway events.
func (b *BridgeTurnExecutor) Execute(ctx context.Context, input TurnExecutionInput, eventCh chan<- gateway.OutboundEvent) error {
	if b.supervisor == nil || !b.supervisor.IsRunning() {
		return fmt.Errorf("layer 4 bridge supervisor is not running")
	}

	payload := b.buildStartTurnPayload(input)

	handle, err := b.supervisor.StartTurn(ctx, input.SessionID, input.TurnID, payload)
	if err != nil {
		eventCh <- gateway.OutboundEvent{
			SessionID: input.SessionID,
			TraceID:   input.TraceID,
			Type:      gateway.EventTurnError,
			AgentName: input.Decision.TargetAgent,
			TextDelta: err.Error(),
			Error:     err.Error(),
		}
		return fmt.Errorf("failed to start bridge turn: %w", err)
	}

	var wg sync.WaitGroup
	wg.Add(4)

	// Stream live tokens to gateway channel
	go func() {
		defer wg.Done()
		for token := range handle.Tokens() {
			eventCh <- gateway.OutboundEvent{
				SessionID: input.SessionID,
				TraceID:   input.TraceID,
				Type:      gateway.EventTokenChunk,
				AgentName: input.Decision.TargetAgent,
				TextDelta: token,
			}
		}
	}()

	// Stream internal thoughts to gateway channel
	go func() {
		defer wg.Done()
		for thought := range handle.Thoughts() {
			eventCh <- gateway.OutboundEvent{
				SessionID: input.SessionID,
				TraceID:   input.TraceID,
				Type:      gateway.EventThoughtChunk,
				AgentName: input.Decision.TargetAgent,
				TextDelta: thought,
			}
		}
	}()

	// Stream tool calls to gateway channel
	go func() {
		defer wg.Done()
		for tc := range handle.ToolCalls() {
			argsBytes, _ := json.Marshal(tc.Arguments)
			eventCh <- gateway.OutboundEvent{
				SessionID: input.SessionID,
				TraceID:   input.TraceID,
				Type:      gateway.EventToolCall,
				AgentName: input.Decision.TargetAgent,
				StatusMsg: fmt.Sprintf("Executing tool %s...", tc.ToolName),
				ToolCall: &gateway.ToolCallInfo{
					CallID:         tc.CallID,
					ToolName:       tc.ToolName,
					Arguments:      tc.Arguments,
					ArgsJSON:       string(argsBytes),
					IdempotencyKey: tc.IdempotencyKey,
				},
			}
		}
	}()

	// Stream tool results to gateway channel
	go func() {
		defer wg.Done()
		for tr := range handle.ToolResults() {
			statusMsg := fmt.Sprintf("Tool %s completed (%dms)", tr.ToolName, tr.DurationMs)
			if tr.IsError {
				statusMsg = fmt.Sprintf("Tool %s failed (%dms)", tr.ToolName, tr.DurationMs)
			}
			eventCh <- gateway.OutboundEvent{
				SessionID: input.SessionID,
				TraceID:   input.TraceID,
				Type:      gateway.EventToolResult,
				AgentName: input.Decision.TargetAgent,
				StatusMsg: statusMsg,
				ToolResult: &gateway.ToolResultInfo{
					CallID:       tr.CallID,
					ToolName:     tr.ToolName,
					ExitCode:     tr.ExitCode,
					Output:       tr.Output,
					ArtifactPath: tr.ArtifactPath,
					DurationMs:   tr.DurationMs,
					IsError:      tr.IsError,
				},
			}
		}
	}()

	// Await completion or error
	var execErr error
	select {
	case <-ctx.Done():
		execErr = ctx.Err()
	case err := <-handle.Errors():
		if err != nil {
			execErr = err
		}
	case complete := <-handle.Complete():
		if complete != nil && complete.Status == "cancelled" {
			execErr = context.Canceled
		}
	}

	wg.Wait()

	if execErr != nil {
		eventCh <- gateway.OutboundEvent{
			SessionID: input.SessionID,
			TraceID:   input.TraceID,
			Type:      gateway.EventTurnError,
			AgentName: input.Decision.TargetAgent,
			TextDelta: execErr.Error(),
			Error:     execErr.Error(),
		}
		return execErr
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: input.SessionID,
		TraceID:   input.TraceID,
		Type:      gateway.EventTurnComplete,
		AgentName: input.Decision.TargetAgent,
	}

	return nil
}

func (b *BridgeTurnExecutor) buildStartTurnPayload(input TurnExecutionInput) *protocol.StartTurnPayload {
	chatMessages := make([]protocol.ChatMessage, 0, len(input.History))
	for _, m := range input.History {
		chatMessages = append(chatMessages, protocol.ChatMessage{
			Role:    string(m.Role),
			Content: m.Content,
		})
	}

	target := input.Decision.TargetAgent
	if target == "" {
		target = "system"
	}

	return &protocol.StartTurnPayload{
		TargetAgent: target,
		Prompt:      input.Prompt,
		Messages:    chatMessages,
		Context: map[string]any{
			"trace_id": input.TraceID,
			"trigger":  string(input.Trigger),
		},
	}
}

// ConvertToSessionMessages translates raw history to session.ChatMessage.
func ConvertToSessionMessages(msgs []protocol.ChatMessage) []session.ChatMessage {
	res := make([]session.ChatMessage, 0, len(msgs))
	for _, m := range msgs {
		res = append(res, session.ChatMessage{
			Role:    m.Role,
			Content: m.Content,
		})
	}
	return res
}

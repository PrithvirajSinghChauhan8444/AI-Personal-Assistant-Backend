package orchestrator

import (
	"context"
	"fmt"
	"time"

	"assistant/src/gateway"
	"assistant/src/orchestrator/router"
	"assistant/src/orchestrator/session"
)

// TurnExecutionInput encapsulates the resolved execution context passed to an executor.
type TurnExecutionInput struct {
	SessionID   string
	TurnID      string
	TraceID     string
	Decision    router.RouteDecision
	Prompt      string
	History     []session.ChatMessage
	Trigger     gateway.TriggerType
	AllowedCaps []string
}

// TurnExecutor defines the contract for executing cognitive turns.
type TurnExecutor interface {
	Execute(ctx context.Context, input TurnExecutionInput, eventCh chan<- gateway.OutboundEvent) error
}

// StandaloneExecutor provides an in-process fallback execution when the Python bridge is not attached.
type StandaloneExecutor struct{}

// NewStandaloneExecutor constructs a StandaloneExecutor.
func NewStandaloneExecutor() *StandaloneExecutor {
	return &StandaloneExecutor{}
}

// Execute processes the turn directly, streaming structured thoughts and token chunks.
func (e *StandaloneExecutor) Execute(ctx context.Context, input TurnExecutionInput, eventCh chan<- gateway.OutboundEvent) error {
	start := time.Now()

	// Emit initial thought chunk explaining the routing path
	eventCh <- gateway.OutboundEvent{
		SessionID: input.SessionID,
		TraceID:   input.TraceID,
		Type:      gateway.EventThoughtChunk,
		AgentName: input.Decision.TargetAgent,
		TextDelta: fmt.Sprintf("Routing mode: %s. Target agent: %s.", input.Decision.Type, input.Decision.TargetAgent),
	}

	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
	}

	// Stream status update
	eventCh <- gateway.OutboundEvent{
		SessionID: input.SessionID,
		TraceID:   input.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: input.Decision.TargetAgent,
		StatusMsg: fmt.Sprintf("Executing task under agent '%s'...", input.Decision.TargetAgent),
	}

	// Stream text delta
	reply := fmt.Sprintf("[%s] Received turn request: %s\n", input.Decision.TargetAgent, input.Prompt)
	eventCh <- gateway.OutboundEvent{
		SessionID: input.SessionID,
		TraceID:   input.TraceID,
		Type:      gateway.EventTokenChunk,
		AgentName: input.Decision.TargetAgent,
		TextDelta: reply,
	}

	// Complete subtask execution
	duration := time.Since(start).Milliseconds()
	eventCh <- gateway.OutboundEvent{
		SessionID: input.SessionID,
		TraceID:   input.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: input.Decision.TargetAgent,
		StatusMsg: fmt.Sprintf("Completed execution in %dms", duration),
	}

	return nil
}

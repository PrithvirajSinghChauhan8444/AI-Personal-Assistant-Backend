package gateway

import "context"

// TurnHandler represents the downstream contract implemented by Layer 2 Orchestrator.
// Layer 1 dispatches normalized turns and submits human-in-the-loop approvals via this interface.
type TurnHandler interface {
	// ExecuteTurn processes the turn and streams outbound events onto eventCh until completion.
	// The caller is responsible for creating and closing eventCh.
	ExecuteTurn(ctx context.Context, req InboundTurnRequest, eventCh chan<- OutboundEvent) error

	// SubmitHITLResponse passes user clearance for a sensitive tool back to Layer 2.
	SubmitHITLResponse(ctx context.Context, resp HITLResponse) error
}

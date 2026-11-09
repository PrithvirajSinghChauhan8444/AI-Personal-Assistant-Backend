package gateway

import (
	"context"
	"errors"
	"fmt"
	"time"
)

var (
	// ErrNilHandler is returned when gateway is constructed without a downstream TurnHandler.
	ErrNilHandler = errors.New("turn handler cannot be nil")
	// ErrEmptyRequestID is returned when an HITL response lacks a RequestID.
	ErrEmptyRequestID = errors.New("request_id is required for HITL response")
)

// Gateway acts as the central ingress and egress boundary for Layer 1.
// It normalizes incoming client traffic and multiplexes outbound streaming events.
type Gateway struct {
	handler TurnHandler
}

// NewGateway creates a verified Gateway backed by a downstream TurnHandler.
func NewGateway(handler TurnHandler) (*Gateway, error) {
	if handler == nil {
		return nil, ErrNilHandler
	}
	return &Gateway{handler: handler}, nil
}

// SubmitTurn normalizes an incoming turn and begins streaming outbound events.
func (g *Gateway) SubmitTurn(ctx context.Context, raw InboundTurnRequest) (<-chan OutboundEvent, InboundTurnRequest, error) {
	req, err := NormalizeInbound(raw)
	if err != nil {
		return nil, InboundTurnRequest{}, fmt.Errorf("normalization failed: %w", err)
	}

	eventCh := make(chan OutboundEvent, 64)
	go g.runTurnPipeline(ctx, req, eventCh)

	return eventCh, req, nil
}

// RespondHITL forwards user approval or rejection back to the active execution turn.
func (g *Gateway) RespondHITL(ctx context.Context, resp HITLResponse) error {
	if resp.RequestID == "" {
		return ErrEmptyRequestID
	}
	if resp.RespondedAt.IsZero() {
		resp.RespondedAt = time.Now().UTC()
	}
	return g.handler.SubmitHITLResponse(ctx, resp)
}

func (g *Gateway) runTurnPipeline(ctx context.Context, req InboundTurnRequest, eventCh chan OutboundEvent) {
	defer close(eventCh)

	err := g.handler.ExecuteTurn(ctx, req, eventCh)
	if err != nil {
		g.emitTurnError(eventCh, req, err)
	}
}

func (g *Gateway) emitTurnError(eventCh chan OutboundEvent, req InboundTurnRequest, err error) {
	eventCh <- OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      EventTurnError,
		AgentName: req.TargetAgent,
		Error:     err.Error(),
	}
}

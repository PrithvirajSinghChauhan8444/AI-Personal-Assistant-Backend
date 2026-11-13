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
// It normalizes incoming client traffic, multiplexes outbound streaming events,
// and coordinates the execution observer telemetry hub.
type Gateway struct {
	handler TurnHandler
	hub     *ObserverHub
}

// NewGateway creates a verified Gateway backed by a downstream TurnHandler and an ObserverHub.
func NewGateway(handler TurnHandler) (*Gateway, error) {
	if handler == nil {
		return nil, ErrNilHandler
	}
	return &Gateway{
		handler: handler,
		hub:     NewObserverHub(),
	}, nil
}

// ObserverHub returns the gateway's execution observer hub.
func (g *Gateway) ObserverHub() *ObserverHub {
	return g.hub
}

// RegisterObserver registers a telemetry or client adapter observer with the gateway.
func (g *Gateway) RegisterObserver(id string, obs ExecutionObserver) error {
	return g.hub.RegisterObserver(id, obs)
}

// UnregisterObserver removes a registered observer by identifier.
func (g *Gateway) UnregisterObserver(id string) {
	g.hub.UnregisterObserver(id)
}

// GetSnapshot retrieves the current point-in-time execution snapshot for a session.
func (g *Gateway) GetSnapshot(sessionID string) (*TurnSnapshot, error) {
	return g.hub.GetSnapshot(sessionID)
}

// GetActiveSnapshots returns current snapshots for all active sessions.
func (g *Gateway) GetActiveSnapshots() []*TurnSnapshot {
	return g.hub.GetActiveSnapshots()
}

// GetTurnLogs retrieves collected operational logs and diagnostic traces for a turn.
func (g *Gateway) GetTurnLogs(turnID string) ([]LogEntry, error) {
	return g.hub.GetTurnLogs(turnID)
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

func (g *Gateway) runTurnPipeline(ctx context.Context, req InboundTurnRequest, clientEventCh chan OutboundEvent) {
	defer close(clientEventCh)

	internalEventCh := make(chan OutboundEvent, 64)
	go func() {
		defer close(internalEventCh)
		err := g.handler.ExecuteTurn(ctx, req, internalEventCh)
		if err != nil {
			g.emitTurnError(internalEventCh, req, err)
		}
	}()

	for ev := range internalEventCh {
		if ev.Timestamp.IsZero() {
			ev.Timestamp = time.Now().UTC()
		}
		g.hub.ProcessEvent(ctx, ev)
		clientEventCh <- ev
	}
}

func (g *Gateway) emitTurnError(eventCh chan<- OutboundEvent, req InboundTurnRequest, err error) {
	eventCh <- OutboundEvent{
		SessionID: req.SessionID,
		TraceID:   req.TraceID,
		Type:      EventTurnError,
		Phase:     PhaseFailed,
		AgentName: req.TargetAgent,
		Timestamp: time.Now().UTC(),
		Error:     err.Error(),
	}
}

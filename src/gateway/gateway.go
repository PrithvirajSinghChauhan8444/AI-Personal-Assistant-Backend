package gateway

import (
	"context"
	"errors"
	"fmt"
	"slices"
	"strings"
	"sync"
	"time"

	"assistant/src/models/genai"
)

var (
	// ErrNilHandler is returned when gateway is constructed without a downstream TurnHandler.
	ErrNilHandler = errors.New("turn handler cannot be nil")
	// ErrEmptyRequestID is returned when an HITL response lacks a RequestID.
	ErrEmptyRequestID = errors.New("request_id is required for HITL response")
)

// Gateway acts as the central ingress and egress boundary for Layer 1.
// It normalizes incoming client traffic, multiplexes outbound streaming events,
// and coordinates the execution observer telemetry hub and prioritized turn queue.
type Gateway struct {
	mu            sync.RWMutex
	handler       TurnHandler
	hub           *ObserverHub
	activeSession string
	queue         *PriorityTurnQueue
	activeAgents  map[string]string // sessionID -> activeAgent
	modelService  *genai.ModelService
}

// NewGateway creates a verified Gateway backed by a downstream TurnHandler and an ObserverHub.
func NewGateway(handler TurnHandler) (*Gateway, error) {
	if handler == nil {
		return nil, ErrNilHandler
	}
	gw := &Gateway{
		handler:      handler,
		hub:          NewObserverHub(),
		activeAgents: make(map[string]string),
		modelService: genai.NewModelService(""),
	}
	gw.queue = NewPriorityTurnQueue(gw.runTurnPipeline)
	gw.queue.Start(context.Background())
	return gw, nil
}

// SetActiveSession registers the active foreground session ID across Layer 1.
func (g *Gateway) SetActiveSession(sessionID string) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.activeSession = sessionID
}

// GetActiveSession retrieves the current active foreground session ID.
func (g *Gateway) GetActiveSession() string {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return g.activeSession
}

// SetActiveAgent sets the active default agent targeting for a specific session.
// Pass "auto", "manager", or "" to reset to orchestrator automatic planning.
func (g *Gateway) SetActiveAgent(sessionID, agentID string) error {
	cleanID := strings.ToLower(strings.TrimSpace(agentID))
	g.mu.Lock()
	defer g.mu.Unlock()

	if cleanID == "auto" || cleanID == "manager" || cleanID == "none" || cleanID == "" {
		delete(g.activeAgents, sessionID)
		return nil
	}

	if !slices.Contains(validAgents, cleanID) {
		return fmt.Errorf("unknown agent %q. Valid agents: %s", agentID, strings.Join(validAgents, ", "))
	}

	g.activeAgents[sessionID] = cleanID
	return nil
}

// GetActiveAgent returns the current active agent targeted for a session, or "auto" if unconfigured.
func (g *Gateway) GetActiveAgent(sessionID string) string {
	g.mu.RLock()
	defer g.mu.RUnlock()
	if agent, ok := g.activeAgents[sessionID]; ok && agent != "" {
		return agent
	}
	return "auto"
}

// GetModelService returns the attached GenAI model service.
func (g *Gateway) GetModelService() *genai.ModelService {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return g.modelService
}

// ListAvailableModels retrieves available models via google.golang.org/genai.
func (g *Gateway) ListAvailableModels(ctx context.Context, forceRefresh bool) ([]genai.ModelInfo, error) {
	if g.modelService == nil {
		return nil, errors.New("genai model service not initialized")
	}
	return g.modelService.ListModels(ctx, forceRefresh)
}

// IsQuotaExceeded checks if an error message indicates rate limit or quota exhaustion (HTTP 429).
func (g *Gateway) IsQuotaExceeded(errMsg string) bool {
	lower := strings.ToLower(errMsg)
	return strings.Contains(lower, "429") ||
		strings.Contains(lower, "resource_exhausted") ||
		strings.Contains(lower, "quotaexceeded") ||
		strings.Contains(lower, "quota exceeded") ||
		strings.Contains(lower, "rate limit") ||
		strings.Contains(lower, "rate_limit") ||
		strings.Contains(lower, "too many requests")
}

// FallbackAndRetry applies a fallback model to the targeted agent and re-dispatches the turn.
func (g *Gateway) FallbackAndRetry(ctx context.Context, raw InboundTurnRequest, fallbackModel string) (<-chan OutboundEvent, InboundTurnRequest, error) {
	agentID := raw.TargetAgent
	if agentID == "" || agentID == "auto" {
		agentID = "manager"
	}

	if err := g.UpdateAgentModel(agentID, fallbackModel); err != nil {
		return nil, raw, fmt.Errorf("failed to update agent model to %q: %w", fallbackModel, err)
	}

	return g.SubmitTurn(ctx, raw)
}

// RegisterAutonomousConsumer binds a listener to receive autonomous turns for a given session.
func (g *Gateway) RegisterAutonomousConsumer(sessionID string, consumer AutonomousConsumerFunc) {
	if g.queue != nil {
		g.queue.RegisterAutonomousConsumer(sessionID, consumer)
	}
}

// UnregisterAutonomousConsumer removes a registered autonomous turn listener.
func (g *Gateway) UnregisterAutonomousConsumer(sessionID string) {
	if g.queue != nil {
		g.queue.UnregisterAutonomousConsumer(sessionID)
	}
}

// Close gracefully terminates background queue workers.
func (g *Gateway) Close() {
	if g.queue != nil {
		g.queue.Stop()
	}
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

// GetActiveSnapshots returns current snapshots for in-flight active sessions.
func (g *Gateway) GetActiveSnapshots() []*TurnSnapshot {
	return g.hub.GetActiveSnapshots()
}

// GetAllSnapshots returns snapshots for all sessions, including completed and failed turns.
func (g *Gateway) GetAllSnapshots() []*TurnSnapshot {
	return g.hub.GetAllSnapshots()
}

// SetPersistentStore attaches a database store to persist logs beyond RAM retention.
func (g *Gateway) SetPersistentStore(store PersistentObserverStore) {
	g.hub.SetPersistentStore(store)
}

// GetTurnLogs retrieves collected operational logs and diagnostic traces for a turn.
func (g *Gateway) GetTurnLogs(turnID string) ([]LogEntry, error) {
	return g.hub.GetTurnLogs(turnID)
}

// SubmitTurn normalizes an incoming turn, enqueues it according to priority, and begins streaming outbound events.
func (g *Gateway) SubmitTurn(ctx context.Context, raw InboundTurnRequest) (<-chan OutboundEvent, InboundTurnRequest, error) {
	g.mu.RLock()
	activeSess := g.activeSession
	g.mu.RUnlock()

	if raw.SessionID == "" && activeSess != "" {
		raw.SessionID = activeSess
	}

	// Apply active switched agent if request has no explicit agent targeting
	if (raw.TargetAgent == "" || raw.TargetAgent == "auto") && raw.SessionID != "" {
		if activeAg := g.GetActiveAgent(raw.SessionID); activeAg != "" && activeAg != "auto" {
			raw.TargetAgent = activeAg
		}
	}

	req, err := NormalizeInbound(raw)
	if err != nil {
		return nil, InboundTurnRequest{}, fmt.Errorf("normalization failed: %w", err)
	}

	priority := PriorityInteractive
	if req.Trigger == TriggerAutonomous || req.Channel == ClientTypeInternal {
		priority = PriorityAutonomous
	}

	if g.queue != nil {
		eventCh, err := g.queue.Enqueue(ctx, req, priority)
		if err != nil {
			return nil, req, fmt.Errorf("failed to enqueue turn: %w", err)
		}
		return eventCh, req, nil
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

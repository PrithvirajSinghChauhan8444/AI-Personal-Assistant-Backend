package orchestrator

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"assistant/src/gateway"
	"assistant/src/orchestrator/safety"
	"assistant/src/orchestrator/session"

	"github.com/google/uuid"
)

// HITLRequest encapsulates the data needed for interactive human approval.
type HITLRequest struct {
	SessionID string
	TurnID    string
	ToolName  string
	ArgsJSON  string
	EventChan chan<- gateway.OutboundEvent
}

// Host coordinates session lifecycle, SQLite persistence, and forwards turns to the Controller.
type Host struct {
	store       session.Store
	controller  *Controller
	pendingHITL sync.Map
}

// HostConfig holds parameters for constructing the Host.
type HostConfig struct {
	Store      session.Store
	Controller *Controller
}

// NewHost creates a new Host backed by a SQLite session store and an Orchestrator Controller.
func NewHost(cfg HostConfig) (*Host, error) {
	if cfg.Store == nil {
		return nil, ErrNilStore
	}

	h := &Host{
		store:      cfg.Store,
		controller: cfg.Controller,
	}

	if h.controller != nil {
		h.controller.SetHITLRequester(h)
	}

	return h, nil
}

// ExecuteTurn handles the inbound turn lifecycle: session resolution, SQLite recording, and controller delegation.
func (h *Host) ExecuteTurn(
	ctx context.Context,
	req gateway.InboundTurnRequest,
	eventCh chan<- gateway.OutboundEvent,
) error {
	turnID := fmt.Sprintf("turn_%d_%s", time.Now().UnixMilli(), uuid.New().String()[:6])

	// 1. Resolve or create persistent session in SQLite
	sess, err := h.store.GetOrCreateSession(ctx, req.SessionID, req.UserID, req.Channel)
	if err != nil {
		return fmt.Errorf("session store failed: %w", err)
	}

	// 2. Persist user message to SQLite
	userMsg := session.ChatMessage{
		SessionID: sess.SessionID,
		TurnID:    turnID,
		Role:      "user",
		AgentName: "user",
		Content:   req.Prompt,
		CreatedAt: time.Now().UTC(),
	}
	if err := h.store.AppendMessage(ctx, userMsg); err != nil {
		return fmt.Errorf("failed to record user message: %w", err)
	}

	// 3. Load conversation history
	history, err := h.store.GetSessionHistory(ctx, sess.SessionID, 50)
	if err != nil {
		return fmt.Errorf("failed to load session history: %w", err)
	}

	// 4. Construct execution context and forward to Controller
	turnCtx := TurnContext{
		SessionID:           sess.SessionID,
		TurnID:              turnID,
		TraceID:             req.TraceID,
		Prompt:              req.Prompt,
		TargetAgent:         req.TargetAgent,
		Trigger:             req.Trigger,
		AllowedCapabilities: req.AllowedCapabilities,
		History:             history,
	}

	assistantReply, err := h.controller.Orchestrate(ctx, turnCtx, eventCh)
	if err != nil {
		return err
	}

	// 5. Persist assistant response to SQLite
	return h.persistAssistantResponse(ctx, sess.SessionID, turnID, assistantReply)
}

// RequestHITL creates a persistent checkpoint in SQLite and alerts the client.
func (h *Host) RequestHITL(ctx context.Context, req HITLRequest) (bool, error) {
	requestID := fmt.Sprintf("req_%s", uuid.New().String())

	cp := session.Checkpoint{
		RequestID:       requestID,
		SessionID:       req.SessionID,
		Status:          session.CheckpointPendingApproval,
		TriggerType:     gateway.TriggerInteractive,
		TargetAgent:     "Manager",
		PendingToolName: req.ToolName,
		PendingToolArgs: req.ArgsJSON,
		TurnStateJSON:   fmt.Sprintf(`{"turn_id":%q,"tool_name":%q}`, req.TurnID, req.ToolName),
		CreatedAt:       time.Now().UTC(),
		UpdatedAt:       time.Now().UTC(),
	}
	if err := h.store.SaveCheckpoint(ctx, cp); err != nil {
		return false, fmt.Errorf("failed to save checkpoint: %w", err)
	}

	respCh := make(chan gateway.HITLResponse, 1)
	h.pendingHITL.Store(requestID, respCh)
	defer h.pendingHITL.Delete(requestID)

	req.EventChan <- gateway.OutboundEvent{
		SessionID: req.SessionID,
		Type:      gateway.EventHITLRequest,
		AgentName: "Manager",
		HITL: &gateway.HITLApprovalPrompt{
			RequestID:        requestID,
			ToolName:         req.ToolName,
			Reason:           fmt.Sprintf("Execution of %q requires human confirmation.", req.ToolName),
			ArgumentsJSON:    req.ArgsJSON,
			AvailableChoices: []string{"Approve", "Deny"},
		},
	}

	select {
	case <-ctx.Done():
		_ = h.store.UpdateCheckpointStatus(context.Background(), requestID, session.CheckpointCancelled)
		return false, ctx.Err()
	case resp := <-respCh:
		auditStatus := "HITL_APPROVED"
		if !resp.Approved {
			auditStatus = "HITL_REJECTED"
		}
		_ = h.store.RecordToolAudit(ctx, session.ToolAuditEntry{
			SessionID: req.SessionID,
			TurnID:    req.TurnID,
			ToolName:  req.ToolName,
			RiskLevel: string(safety.RiskHigh),
			Status:    auditStatus,
			CreatedAt: time.Now().UTC(),
		})
		return resp.Approved, nil
	}
}

// SubmitHITLResponse resolves a pending approval and resumes execution.
func (h *Host) SubmitHITLResponse(ctx context.Context, resp gateway.HITLResponse) error {
	chRaw, loaded := h.pendingHITL.LoadAndDelete(resp.RequestID)
	if !loaded {
		return h.handleOfflineCheckpointUpdate(ctx, resp)
	}

	ch, ok := chRaw.(chan gateway.HITLResponse)
	if !ok {
		return errors.New("internal error: invalid HITL channel type in registry")
	}

	status := session.CheckpointResumed
	if !resp.Approved {
		status = session.CheckpointCancelled
	}
	_ = h.store.UpdateCheckpointStatus(ctx, resp.RequestID, status)

	select {
	case ch <- resp:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func (h *Host) handleOfflineCheckpointUpdate(ctx context.Context, resp gateway.HITLResponse) error {
	status := session.CheckpointResumed
	if !resp.Approved {
		status = session.CheckpointCancelled
	}
	err := h.store.UpdateCheckpointStatus(ctx, resp.RequestID, status)
	if errors.Is(err, session.ErrCheckpointNotFound) {
		return ErrPendingApprovalNotFound
	}
	return err
}

func (h *Host) persistAssistantResponse(ctx context.Context, sessionID, turnID, content string) error {
	if content == "" {
		return nil
	}
	return h.store.AppendMessage(ctx, session.ChatMessage{
		SessionID: sessionID,
		TurnID:    turnID,
		Role:      "assistant",
		AgentName: "Manager",
		Content:   content,
		CreatedAt: time.Now().UTC(),
	})
}

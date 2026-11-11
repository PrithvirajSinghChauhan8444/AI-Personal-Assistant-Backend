package orchestrator

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"assistant/src/gateway"
	"assistant/src/orchestrator/planner"
	"assistant/src/orchestrator/router"
	"assistant/src/orchestrator/safety"
	"assistant/src/orchestrator/scheduler"
	"assistant/src/orchestrator/session"
)

// HITLRequester defines the contract for pausing execution and requesting human approval.
type HITLRequester interface {
	RequestHITL(ctx context.Context, req HITLRequest) (bool, error)
}

// TurnContext provides the execution context forwarded from the Host to the Controller.
type TurnContext struct {
	SessionID           string
	TurnID              string
	TraceID             string
	Prompt              string
	TargetAgent         string
	Trigger             gateway.TriggerType
	AllowedCapabilities []string
	History             []session.ChatMessage
}

// Controller is the real orchestrator: manages the Manager Agent (LLM), Scheduler (DAG), Gatekeeper, and Workers.
type Controller struct {
	manager       *planner.ManagerAgent
	gatekeeper    *safety.Gatekeeper
	executor      TurnExecutor
	spillover     *ArtifactSpillover
	hitlRequester HITLRequester
}

// ControllerConfig configures the Controller.
type ControllerConfig struct {
	Manager        *planner.ManagerAgent
	Gatekeeper     *safety.Gatekeeper
	Executor       TurnExecutor
	Spillover      *ArtifactSpillover
	HITLRequester  HITLRequester
	PromptFilePath string
}

// NewController initializes the real orchestrator controller.
func NewController(cfg ControllerConfig) *Controller {
	gk := cfg.Gatekeeper
	if gk == nil {
		gk = safety.NewGatekeeper()
	}

	mgr := cfg.Manager
	if mgr == nil {
		mgr = planner.NewManagerAgent(nil, nil, cfg.PromptFilePath)
	}

	exec := cfg.Executor
	if exec == nil {
		exec = NewStandaloneExecutor()
	}

	spill := cfg.Spillover
	if spill == nil {
		spill = NewArtifactSpillover("workspace/artifacts", DefaultSpilloverThresholdBytes)
	}

	return &Controller{
		manager:       mgr,
		gatekeeper:    gk,
		executor:      exec,
		spillover:     spill,
		hitlRequester: cfg.HITLRequester,
	}
}

// SetHITLRequester binds the host approval handler to the controller.
func (c *Controller) SetHITLRequester(requester HITLRequester) {
	c.hitlRequester = requester
}

// Orchestrate executes the cognitive planning and DAG execution lifecycle.
func (c *Controller) Orchestrate(
	ctx context.Context,
	turn TurnContext,
	eventCh chan<- gateway.OutboundEvent,
) (string, error) {
	startTime := time.Now()

	// 1. Emit planning start notification
	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: "Manager",
		StatusMsg: "Decomposing user request into actionable TaskPlan DAG...",
	}

	// 2. LLM Cognitive Planning via Manager Agent
	plan, err := c.planTurn(ctx, turn)
	if err != nil {
		return "", fmt.Errorf("manager planning failed: %w", err)
	}

	c.emitPlanThought(turn.SessionID, turn.TraceID, plan, eventCh)

	// 3. Task Scheduler walks the DAG
	sched := scheduler.NewTaskScheduler(plan, scheduler.Config{
		AllowParallel:     true,
		MaxParallel:       4,
		AutoHealDeadlocks: true,
	})

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: "Scheduler",
		StatusMsg: fmt.Sprintf("Walking DAG and dispatching %d subtask(s)...", len(plan.SubTasks)),
	}

	accumulator := &stringAccumulator{}
	c.executeScheduledDAG(ctx, sched, turn, accumulator, eventCh)

	// 4. Emit final turn completion event with telemetry
	duration := time.Since(startTime).Milliseconds()
	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventTurnComplete,
		AgentName: "Orchestrator",
		Metrics: &gateway.TurnMetrics{
			ModelName:        "layer2-orchestrator",
			PromptTokens:     int32(len(turn.Prompt) / 4),
			CompletionTokens: int32(len(accumulator.String()) / 4),
			TotalDurationMs:  duration,
		},
	}

	return accumulator.String(), nil
}

func (c *Controller) planTurn(ctx context.Context, turn TurnContext) (*planner.TaskPlan, error) {
	var contextData map[string]interface{}
	if turn.TargetAgent != "" && turn.TargetAgent != "auto" {
		contextData = map[string]interface{}{
			"user_hinted_target": turn.TargetAgent,
		}
	}

	plan, err := c.manager.Plan(ctx, turn.Prompt, contextData)
	if err != nil || plan == nil {
		return nil, fmt.Errorf("manager returned nil or error: %w", err)
	}
	return plan, nil
}

func (c *Controller) emitPlanThought(sessionID, traceID string, plan *planner.TaskPlan, eventCh chan<- gateway.OutboundEvent) {
	var planSummary []string
	for _, st := range plan.SubTasks {
		planSummary = append(planSummary, fmt.Sprintf("%s (@%s)", st.ID, st.GetWorker()))
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: sessionID,
		TraceID:   traceID,
		Type:      gateway.EventThoughtChunk,
		AgentName: "Manager",
		TextDelta: fmt.Sprintf("Manager planned %d subtasks: [%s]", len(plan.SubTasks), strings.Join(planSummary, ", ")),
	}
}

func (c *Controller) executeScheduledDAG(
	ctx context.Context,
	sched *scheduler.TaskScheduler,
	turn TurnContext,
	accumulator *stringAccumulator,
	eventCh chan<- gateway.OutboundEvent,
) {
	for !sched.IsComplete() {
		readyTasks := sched.GetExecutableTasks()
		if len(readyTasks) == 0 {
			break
		}

		var wg sync.WaitGroup
		for _, task := range readyTasks {
			wg.Add(1)
			go func(t *planner.SubTask) {
				defer wg.Done()
				c.executeSubTask(ctx, sched, t, turn, accumulator, eventCh)
			}(task)
		}
		wg.Wait()
	}
}

func (c *Controller) executeSubTask(
	ctx context.Context,
	sched *scheduler.TaskScheduler,
	t *planner.SubTask,
	turn TurnContext,
	accumulator *stringAccumulator,
	eventCh chan<- gateway.OutboundEvent,
) {
	_ = sched.MarkInProgress(t.ID)
	targetWorker := t.GetWorker()

	// Safety Gatekeeper check
	eval := c.gatekeeper.Evaluate(targetWorker, turn.Trigger, turn.AllowedCapabilities)
	if !eval.Allowed {
		_ = sched.MarkFailed(t.ID, eval.Reason)
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			Type:      gateway.EventTurnError,
			AgentName: targetWorker,
			Error:     eval.Reason,
		}
		return
	}

	// Human-In-The-Loop check if required
	if eval.RequiresHITL && c.hitlRequester != nil {
		hitlReq := HITLRequest{
			SessionID: turn.SessionID,
			TurnID:    turn.TurnID,
			ToolName:  targetWorker,
			ArgsJSON:  fmt.Sprintf(`{"task_id":%q,"description":%q}`, t.ID, t.Description),
			EventChan: eventCh,
		}
		approved, err := c.hitlRequester.RequestHITL(ctx, hitlReq)
		if err != nil || !approved {
			_ = sched.MarkFailed(t.ID, "subtask execution rejected by user or cancelled")
			return
		}
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: targetWorker,
		StatusMsg: fmt.Sprintf("Executing subtask %s: %s", t.ID, t.Description),
	}

	taskPrompt := c.buildTaskPrompt(t, sched)
	taskDecision := router.RouteDecision{
		Type:        router.RouteFastPath,
		TargetAgent: targetWorker,
		Prompt:      taskPrompt,
	}

	subtaskOutput := &stringAccumulator{}
	interceptorCh := make(chan gateway.OutboundEvent, 16)
	var forwardWg sync.WaitGroup
	forwardWg.Add(1)

	go func() {
		defer forwardWg.Done()
		for ev := range interceptorCh {
			if ev.Type == gateway.EventTokenChunk && ev.TextDelta != "" {
				subtaskOutput.WriteString(ev.TextDelta)
				accumulator.WriteString(ev.TextDelta)
			}
			eventCh <- ev
		}
	}()

	input := TurnExecutionInput{
		SessionID:   turn.SessionID,
		TurnID:      turn.TurnID,
		TraceID:     turn.TraceID,
		Decision:    taskDecision,
		Prompt:      taskPrompt,
		History:     turn.History,
		Trigger:     turn.Trigger,
		AllowedCaps: turn.AllowedCapabilities,
	}

	err := c.executor.Execute(ctx, input, interceptorCh)
	close(interceptorCh)
	forwardWg.Wait()

	if err != nil {
		_ = sched.MarkFailed(t.ID, err.Error())
		return
	}

	c.finalizeSubTaskOutput(t, subtaskOutput.String(), sched, eventCh, turn.SessionID)
}

func (c *Controller) buildTaskPrompt(t *planner.SubTask, sched *scheduler.TaskScheduler) string {
	prompt := t.Description
	depOutputs := sched.GetDependencyOutputs(t.ID)
	if len(depOutputs) > 0 {
		var depContext strings.Builder
		depContext.WriteString("\n\n--- Input from Prerequisite Subtasks ---")
		for depID, out := range depOutputs {
			depContext.WriteString(fmt.Sprintf("\n[%s Result]:\n%s", depID, out))
		}
		prompt += depContext.String()
	}
	return prompt
}

func (c *Controller) finalizeSubTaskOutput(
	t *planner.SubTask,
	rawOutput string,
	sched *scheduler.TaskScheduler,
	eventCh chan<- gateway.OutboundEvent,
	sessionID string,
) {
	targetWorker := t.GetWorker()
	finalOutput, artifactPath, spilled, spillErr := c.spillover.Process(rawOutput)
	if spillErr == nil && spilled {
		eventCh <- gateway.OutboundEvent{
			SessionID: sessionID,
			Type:      gateway.EventStatusUpdate,
			AgentName: targetWorker,
			StatusMsg: fmt.Sprintf("Subtask output spilled to artifact pointer: %s", artifactPath),
		}
		_ = sched.MarkCompleted(t.ID, finalOutput)
		return
	}

	if rawOutput == "" {
		rawOutput = "completed successfully"
	}
	_ = sched.MarkCompleted(t.ID, rawOutput)
	eventCh <- gateway.OutboundEvent{
		SessionID: sessionID,
		Type:      gateway.EventStatusUpdate,
		AgentName: targetWorker,
		StatusMsg: fmt.Sprintf("Subtask %s completed successfully.", t.ID),
	}
}

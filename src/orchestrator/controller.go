package orchestrator

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"

	"assistant/src/gateway"
	"assistant/src/orchestrator/manifest"
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
	manager          *planner.ManagerAgent
	gatekeeper       *safety.Gatekeeper
	executor         TurnExecutor
	spillover        *ArtifactSpillover
	hitlRequester    HITLRequester
	activeDAGs       sync.Map // sessionID -> *activeDAGContext
	interceptors     sync.Map // id -> TaskInterceptor
	agentsConfigPath string
}

type inFlightTaskInfo struct {
	startedAt    time.Time
	worker       string
	inputContext map[string]interface{}
}

type activeDAGContext struct {
	sessionID     string
	turnID        string
	sched         *scheduler.TaskScheduler
	inFlightTasks map[string]*inFlightTaskInfo
	inFlightMu    sync.RWMutex
}

// ControllerConfig configures the Controller.
type ControllerConfig struct {
	Manager          *planner.ManagerAgent
	Gatekeeper       *safety.Gatekeeper
	Executor         TurnExecutor
	Spillover        *ArtifactSpillover
	HITLRequester    HITLRequester
	PromptFilePath   string
	AgentsConfigPath string
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

	agentsCfgPath := cfg.AgentsConfigPath
	if agentsCfgPath == "" {
		agentsCfgPath = "config/agents.json"
	}

	return &Controller{
		manager:          mgr,
		gatekeeper:       gk,
		executor:         exec,
		spillover:        spill,
		hitlRequester:    cfg.HITLRequester,
		agentsConfigPath: agentsCfgPath,
	}
}

// SetHITLRequester binds the host approval handler to the controller.
func (c *Controller) SetHITLRequester(requester HITLRequester) {
	c.hitlRequester = requester
}

// RegisterTaskInterceptor binds an interceptor to subtask execution hooks.
func (c *Controller) RegisterTaskInterceptor(id string, interceptor TaskInterceptor) {
	if id != "" && interceptor != nil {
		c.interceptors.Store(id, interceptor)
	}
}

// UnregisterTaskInterceptor unbinds an interceptor by ID.
func (c *Controller) UnregisterTaskInterceptor(id string) {
	c.interceptors.Delete(id)
}

// GetDAGSnapshot retrieves the live topological execution graph of the active turn for a session.
func (c *Controller) GetDAGSnapshot(sessionID string) (*DAGExecutionSnapshot, error) {
	dagRaw, ok := c.activeDAGs.Load(sessionID)
	if !ok {
		return nil, ErrNoActiveDAG
	}
	dagCtx := dagRaw.(*activeDAGContext)
	plan := dagCtx.sched.GetPlan()
	if plan == nil {
		return nil, ErrNoActiveDAG
	}

	subtasks := dagCtx.sched.GetSubtasks()
	snapshot := &DAGExecutionSnapshot{
		PlanID:         plan.PlanID,
		PrimaryGoal:    plan.PrimaryGoal,
		TotalTasks:     len(subtasks),
		DependencyTree: make(map[string][]string),
	}

	dagCtx.inFlightMu.RLock()
	defer dagCtx.inFlightMu.RUnlock()

	for _, st := range subtasks {
		snapshot.DependencyTree[st.ID] = st.DependsOn
		switch st.Status {
		case planner.StatusCompleted:
			snapshot.CompletedTasks++
		case planner.StatusFailed, planner.StatusAborted:
			snapshot.FailedTasks++
		case planner.StatusPending:
			snapshot.PendingTasks = append(snapshot.PendingTasks, st.ID)
		case planner.StatusInProgress:
			info := dagCtx.inFlightTasks[st.ID]
			var elapsed int64
			var inputCtx map[string]interface{}
			worker := st.GetWorker()
			if info != nil {
				elapsed = time.Since(info.startedAt).Milliseconds()
				inputCtx = info.inputContext
				if info.worker != "" {
					worker = info.worker
				}
			}
			snapshot.InFlightTasks = append(snapshot.InFlightTasks, InFlightTaskSnapshot{
				SubtaskID:    st.ID,
				Worker:       worker,
				ElapsedMs:    elapsed,
				InputContext: inputCtx,
			})
		}
	}

	return snapshot, nil
}

// ResumeDAG rehydrates and continues execution of a suspended TaskPlan DAG.
func (c *Controller) ResumeDAG(
	ctx context.Context,
	state CheckpointTurnState,
	eventCh chan<- gateway.OutboundEvent,
) (string, error) {
	if state.Plan == nil || state.TurnContext == nil {
		return "", errors.New("cannot resume DAG: nil plan or turn context")
	}

	turn := *state.TurnContext
	sched := scheduler.NewTaskScheduler(state.Plan, scheduler.Config{
		AllowParallel:     true,
		MaxParallel:       4,
		AutoHealDeadlocks: true,
	})

	// Restore completed outputs
	for id, output := range state.CompletedOutputs {
		_ = sched.MarkCompleted(id, output)
	}

	// Register active DAG for observability
	dagCtx := &activeDAGContext{
		sessionID:     turn.SessionID,
		turnID:        turn.TurnID,
		sched:         sched,
		inFlightTasks: make(map[string]*inFlightTaskInfo),
	}
	c.activeDAGs.Store(turn.SessionID, dagCtx)
	defer c.activeDAGs.Delete(turn.SessionID)

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventPhaseChange,
		Phase:     gateway.PhaseExecuting,
		AgentName: "Scheduler",
		Timestamp: time.Now().UTC(),
		StatusMsg: fmt.Sprintf("Resuming DAG execution from checkpoint for %d subtask(s)...", len(state.Plan.SubTasks)),
	}

	accumulator := &stringAccumulator{}
	// Preload any completed outputs into accumulator
	for _, st := range state.Plan.SubTasks {
		if st.Status == planner.StatusCompleted && st.Output != "" {
			accumulator.WriteString(fmt.Sprintf("[%s Result]:\n%s\n\n", st.ID, st.Output))
		}
	}

	c.executeScheduledDAG(ctx, sched, turn, accumulator, eventCh)

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventPhaseChange,
		Phase:     gateway.PhaseCompleted,
		AgentName: "Orchestrator",
		Timestamp: time.Now().UTC(),
		StatusMsg: "Resumed turn completed successfully.",
	}

	finalResponse := accumulator.String()
	if c.isSummarizerEnabled() && sched.IsComplete() && turn.TargetAgent != "summarizer" {
		summarized, err := c.runSummarizer(ctx, turn, sched, accumulator.String(), eventCh)
		if err == nil && strings.TrimSpace(summarized) != "" {
			finalResponse = summarized
		}
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventTurnComplete,
		AgentName: "Orchestrator",
		Timestamp: time.Now().UTC(),
		Metrics: &gateway.TurnMetrics{
			ModelName:        "layer2-orchestrator",
			PromptTokens:     int32(len(turn.Prompt) / 4),
			CompletionTokens: int32(len(finalResponse) / 4),
		},
	}

	return finalResponse, nil
}

// Orchestrate executes the cognitive planning and DAG execution lifecycle.
func (c *Controller) Orchestrate(
	ctx context.Context,
	turn TurnContext,
	eventCh chan<- gateway.OutboundEvent,
) (string, error) {
	startTime := time.Now()

	// 1. Transition to Planning phase and emit planning start notification
	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventPhaseChange,
		Phase:     gateway.PhasePlanning,
		AgentName: "Manager",
		Timestamp: startTime,
		StatusMsg: "Entering Planning phase. Decomposing user request...",
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: "Manager",
		Timestamp: startTime,
		StatusMsg: "Decomposing user request into actionable TaskPlan DAG...",
	}

	// 2. LLM Cognitive Planning via Manager Agent
	plan, err := c.planTurn(ctx, turn)
	if err != nil {
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    turn.TurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventPlanDiagnostic,
			AgentName: "Manager",
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Planning diagnostic: %v", err),
			Diagnostic: &gateway.PlanDiagnosticInfo{
				Goal:              turn.Prompt,
				Reason:            fmt.Sprintf("Manager planning failed: %v", err),
				FallbackTriggered: false,
				Error:             err.Error(),
			},
		}
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    turn.TurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventPhaseChange,
			Phase:     gateway.PhaseFailed,
			AgentName: "Manager",
			Timestamp: time.Now().UTC(),
			StatusMsg: "Planning failed.",
		}
		return "", fmt.Errorf("manager planning failed: %w", err)
	}

	// Emit structured PlanCreated event
	subtaskItems := make([]gateway.SubtaskItemInfo, len(plan.SubTasks))
	for i, st := range plan.SubTasks {
		subtaskItems[i] = gateway.SubtaskItemInfo{
			ID:               st.ID,
			Description:      st.Description,
			AssignedWorker:   st.GetWorker(),
			DependsOn:        st.DependsOn,
			Status:           string(st.Status),
			ConfidenceScore:  st.ConfidenceScore,
			ConfidenceReason: st.ConfidenceReason,
			InputContext:     st.InputContext,
		}
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventPlanCreated,
		AgentName: "Manager",
		Timestamp: time.Now().UTC(),
		Plan: &gateway.PlanInfo{
			PlanID:      plan.PlanID,
			PrimaryGoal: plan.PrimaryGoal,
			SubTasks:    subtaskItems,
		},
	}

	c.emitPlanThought(turn.SessionID, turn.TraceID, plan, eventCh)

	// Emit thought completion boundary for the planning phase
	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventThoughtComplete,
		AgentName: "Manager",
		Timestamp: time.Now().UTC(),
		StatusMsg: "Manager planning completed. Beginning task execution.",
	}

	// 3. Task Scheduler walks the DAG
	sched := scheduler.NewTaskScheduler(plan, scheduler.Config{
		AllowParallel:     true,
		MaxParallel:       4,
		AutoHealDeadlocks: true,
	})

	dagCtx := &activeDAGContext{
		sessionID:     turn.SessionID,
		turnID:        turn.TurnID,
		sched:         sched,
		inFlightTasks: make(map[string]*inFlightTaskInfo),
	}
	c.activeDAGs.Store(turn.SessionID, dagCtx)
	defer c.activeDAGs.Delete(turn.SessionID)

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventPhaseChange,
		Phase:     gateway.PhaseExecuting,
		AgentName: "Scheduler",
		Timestamp: time.Now().UTC(),
		StatusMsg: fmt.Sprintf("Walking DAG and dispatching %d subtask(s)...", len(plan.SubTasks)),
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: "Scheduler",
		Timestamp: time.Now().UTC(),
		StatusMsg: fmt.Sprintf("Walking DAG and dispatching %d subtask(s)...", len(plan.SubTasks)),
	}

	accumulator := &stringAccumulator{}
	c.executeScheduledDAG(ctx, sched, turn, accumulator, eventCh)

	finalResponse := accumulator.String()
	if c.isSummarizerEnabled() && sched.IsComplete() && turn.TargetAgent != "summarizer" {
		summarized, err := c.runSummarizer(ctx, turn, sched, accumulator.String(), eventCh)
		if err == nil && strings.TrimSpace(summarized) != "" {
			finalResponse = summarized
		}
	}

	// 4. Emit final turn completion event with telemetry
	duration := time.Since(startTime).Milliseconds()

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventPhaseChange,
		Phase:     gateway.PhaseCompleted,
		AgentName: "Orchestrator",
		Timestamp: time.Now().UTC(),
		StatusMsg: "Turn completed successfully.",
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    turn.TurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventTurnComplete,
		AgentName: "Orchestrator",
		Timestamp: time.Now().UTC(),
		Metrics: &gateway.TurnMetrics{
			ModelName:        "layer2-orchestrator",
			PromptTokens:     int32(len(turn.Prompt) / 4),
			CompletionTokens: int32(len(finalResponse) / 4),
			TotalDurationMs:  duration,
		},
	}

	return finalResponse, nil
}

func (c *Controller) planTurn(ctx context.Context, turn TurnContext) (*planner.TaskPlan, error) {
	var contextData map[string]interface{}
	if turn.TargetAgent != "" && turn.TargetAgent != "auto" {
		contextData = map[string]interface{}{
			"user_hinted_target": turn.TargetAgent,
		}
	}

	plan, err := c.manager.Plan(ctx, turn.Prompt, contextData, turn.History)
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
	subtaskStart := time.Now()
	_ = sched.MarkInProgress(t.ID)
	targetWorker := strings.ToLower(strings.TrimSpace(t.GetWorker()))

	subtaskTurnID := turn.TurnID
	if t.ID != "" {
		subtaskTurnID = fmt.Sprintf("%s_%s", turn.TurnID, t.ID)
	}

	dagRaw, hasDAG := c.activeDAGs.Load(turn.SessionID)
	var dagCtx *activeDAGContext
	if hasDAG {
		dagCtx = dagRaw.(*activeDAGContext)
		dagCtx.inFlightMu.Lock()
		dagCtx.inFlightTasks[t.ID] = &inFlightTaskInfo{
			startedAt:    subtaskStart,
			worker:       targetWorker,
			inputContext: t.InputContext,
		}
		dagCtx.inFlightMu.Unlock()
	}
	defer func() {
		if dagCtx != nil {
			dagCtx.inFlightMu.Lock()
			delete(dagCtx.inFlightTasks, t.ID)
			dagCtx.inFlightMu.Unlock()
		}
	}()

	// Execute BeforeSubtask interceptors
	var beforeErr error
	c.interceptors.Range(func(key, value interface{}) bool {
		if interceptor, ok := value.(TaskInterceptor); ok {
			if err := interceptor.BeforeSubtask(ctx, t); err != nil {
				beforeErr = err
				return false
			}
		}
		return true
	})
	if beforeErr != nil {
		_ = sched.MarkFailed(t.ID, beforeErr.Error())
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    subtaskTurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventSubtaskFailed,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Subtask %s denied by interceptor: %v", t.ID, beforeErr),
			Error:     beforeErr.Error(),
			Subtask: &gateway.SubtaskEventInfo{
				SubtaskID:   t.ID,
				Worker:      targetWorker,
				Description: t.Description,
				Status:      "FAILED",
				Error:       beforeErr.Error(),
			},
		}
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    subtaskTurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventTurnError,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			Error:     beforeErr.Error(),
		}
		return
	}

	// Verify that the targetWorker is currently active and enabled in configuration
	if targetWorker != "echo" && targetWorker != "system" {
		activeManifests, err := manifest.LoadActiveManifests("", "")
		if err == nil && len(activeManifests) > 0 {
			if _, isActive := activeManifests[targetWorker]; !isActive {
				errReason := fmt.Sprintf("subtask %s requires worker %q which is currently disabled in config/agents.json. Please enable %q to execute this task", t.ID, targetWorker, targetWorker)
				_ = sched.MarkFailed(t.ID, errReason)
				eventCh <- gateway.OutboundEvent{
					SessionID: turn.SessionID,
					TurnID:    subtaskTurnID,
					TraceID:   turn.TraceID,
					Type:      gateway.EventSubtaskFailed,
					AgentName: targetWorker,
					Timestamp: time.Now().UTC(),
					StatusMsg: errReason,
					Error:     errReason,
					Subtask: &gateway.SubtaskEventInfo{
						SubtaskID:   t.ID,
						Worker:      targetWorker,
						Description: t.Description,
						Status:      "FAILED",
						Error:       errReason,
					},
				}
				eventCh <- gateway.OutboundEvent{
					SessionID: turn.SessionID,
					TurnID:    subtaskTurnID,
					TraceID:   turn.TraceID,
					Type:      gateway.EventTurnError,
					AgentName: targetWorker,
					Timestamp: time.Now().UTC(),
					Error:     errReason,
				}
				return
			}
		}
	}

	// Safety Gatekeeper check
	eval := c.gatekeeper.Evaluate(targetWorker, turn.Trigger, turn.AllowedCapabilities)
	if !eval.Allowed {
		_ = sched.MarkFailed(t.ID, eval.Reason)
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    subtaskTurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventSubtaskFailed,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Subtask %s denied by safety gatekeeper: %s", t.ID, eval.Reason),
			Error:     eval.Reason,
			Subtask: &gateway.SubtaskEventInfo{
				SubtaskID:   t.ID,
				Worker:      targetWorker,
				Description: t.Description,
				Status:      "FAILED",
				Error:       eval.Reason,
			},
		}
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    subtaskTurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventTurnError,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			Error:     eval.Reason,
		}
		return
	}

	// Human-In-The-Loop check if required
	if eval.RequiresHITL && c.hitlRequester != nil {
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    subtaskTurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventPhaseChange,
			Phase:     gateway.PhaseWaitingApproval,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Pausing execution. Subtask %s requires human approval.", t.ID),
		}

		// Gather completed outputs from completed subtasks
		completedOutputs := make(map[string]string)
		for _, st := range sched.GetSubtasks() {
			if st.Status == planner.StatusCompleted && st.Output != "" {
				completedOutputs[st.ID] = st.Output
			}
		}

		hitlReq := HITLRequest{
			SessionID:        turn.SessionID,
			TurnID:           subtaskTurnID,
			ToolName:         targetWorker,
			ArgsJSON:         fmt.Sprintf(`{"task_id":%q,"description":%q}`, t.ID, t.Description),
			EventChan:        eventCh,
			SubtaskID:        t.ID,
			Plan:             sched.GetPlan(),
			CompletedOutputs: completedOutputs,
			TurnContext:      &turn,
		}
		approved, err := c.hitlRequester.RequestHITL(ctx, hitlReq)
		if err != nil || !approved {
			_ = sched.MarkFailed(t.ID, "subtask execution rejected by user or cancelled")
			eventCh <- gateway.OutboundEvent{
				SessionID: turn.SessionID,
				TurnID:    subtaskTurnID,
				TraceID:   turn.TraceID,
				Type:      gateway.EventSubtaskFailed,
				AgentName: targetWorker,
				Timestamp: time.Now().UTC(),
				StatusMsg: fmt.Sprintf("Subtask %s rejected or cancelled.", t.ID),
				Subtask: &gateway.SubtaskEventInfo{
					SubtaskID:   t.ID,
					Worker:      targetWorker,
					Description: t.Description,
					Status:      "FAILED",
					Error:       "subtask execution rejected by user or cancelled",
				},
			}
			return
		}

		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    subtaskTurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventPhaseChange,
			Phase:     gateway.PhaseExecuting,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Human approval granted. Resuming execution of subtask %s.", t.ID),
		}
	}

	taskPrompt := c.buildTaskPrompt(t, sched)
	taskDecision := router.RouteDecision{
		Type:        router.RouteFastPath,
		TargetAgent: targetWorker,
		Prompt:      taskPrompt,
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    subtaskTurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventSubtaskStart,
		AgentName: targetWorker,
		Timestamp: time.Now().UTC(),
		StatusMsg: fmt.Sprintf("Executing subtask %s: %s", t.ID, t.Description),
		Subtask: &gateway.SubtaskEventInfo{
			SubtaskID:    t.ID,
			Worker:       targetWorker,
			Description:  t.Description,
			Status:       "IN_PROGRESS",
			DependsOn:    t.DependsOn,
			InputPrompt:  taskPrompt,
			InputContext: t.InputContext,
		},
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    subtaskTurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: targetWorker,
		Timestamp: time.Now().UTC(),
		StatusMsg: fmt.Sprintf("Executing subtask %s: %s", t.ID, t.Description),
	}

	subtaskOutput := &stringAccumulator{}
	interceptorCh := make(chan gateway.OutboundEvent, 16)
	var forwardWg sync.WaitGroup
	forwardWg.Add(1)

	go func() {
		defer forwardWg.Done()
		for ev := range interceptorCh {
			if ev.TurnID == "" {
				ev.TurnID = subtaskTurnID
			}
			if ev.Type == gateway.EventTokenChunk && ev.TextDelta != "" {
				subtaskOutput.WriteString(ev.TextDelta)
				accumulator.WriteString(ev.TextDelta)
			}
			// Subtask execution completes a subtask, not the entire turn.
			// Prevent inner bridge completion or error from prematurely finalizing the gateway turn.
			if ev.Type == gateway.EventTurnComplete || ev.Type == gateway.EventTurnError {
				continue
			}
			eventCh <- ev
		}
	}()

	input := TurnExecutionInput{
		SessionID:   turn.SessionID,
		TurnID:      subtaskTurnID,
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

	durationMs := time.Since(subtaskStart).Milliseconds()

	if err != nil {
		_ = sched.MarkFailed(t.ID, err.Error())
		eventCh <- gateway.OutboundEvent{
			SessionID: turn.SessionID,
			TurnID:    subtaskTurnID,
			TraceID:   turn.TraceID,
			Type:      gateway.EventSubtaskFailed,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Subtask %s failed: %v", t.ID, err),
			Error:     err.Error(),
			Subtask: &gateway.SubtaskEventInfo{
				SubtaskID:   t.ID,
				Worker:      targetWorker,
				Description: t.Description,
				Status:      "FAILED",
				DurationMs:  durationMs,
				Error:       err.Error(),
			},
		}

		subResult := SubtaskResult{
			Output:     subtaskOutput.String(),
			DurationMs: durationMs,
			Error:      err,
		}
		c.interceptors.Range(func(key, value interface{}) bool {
			if interceptor, ok := value.(TaskInterceptor); ok {
				interceptor.AfterSubtask(ctx, t, &subResult)
			}
			return true
		})
		return
	}

	artifactPath := c.finalizeSubTaskOutput(t, subtaskOutput.String(), sched, eventCh, turn.SessionID, subtaskTurnID, durationMs)

	subResult := SubtaskResult{
		Output:       subtaskOutput.String(),
		ArtifactPath: artifactPath,
		DurationMs:   durationMs,
		Error:        nil,
	}
	c.interceptors.Range(func(key, value interface{}) bool {
		if interceptor, ok := value.(TaskInterceptor); ok {
			interceptor.AfterSubtask(ctx, t, &subResult)
		}
		return true
	})
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
	subtaskTurnID string,
	durationMs int64,
) string {
	targetWorker := t.GetWorker()
	finalOutput, artifactPath, spilled, spillErr := c.spillover.Process(rawOutput)
	if spillErr == nil && spilled {
		eventCh <- gateway.OutboundEvent{
			SessionID: sessionID,
			TurnID:    subtaskTurnID,
			Type:      gateway.EventStatusUpdate,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Subtask output spilled to artifact pointer: %s", artifactPath),
		}
		_ = sched.MarkCompleted(t.ID, finalOutput)
		eventCh <- gateway.OutboundEvent{
			SessionID: sessionID,
			TurnID:    subtaskTurnID,
			Type:      gateway.EventSubtaskComplete,
			AgentName: targetWorker,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Subtask %s completed (spilled to artifact).", t.ID),
			Subtask: &gateway.SubtaskEventInfo{
				SubtaskID:    t.ID,
				Worker:       targetWorker,
				Description:  t.Description,
				Status:       "COMPLETED",
				Output:       finalOutput,
				ArtifactPath: artifactPath,
				DurationMs:   durationMs,
			},
		}
		return artifactPath
	}

	if rawOutput == "" {
		rawOutput = "completed successfully"
	}
	_ = sched.MarkCompleted(t.ID, rawOutput)

	eventCh <- gateway.OutboundEvent{
		SessionID: sessionID,
		TurnID:    subtaskTurnID,
		Type:      gateway.EventSubtaskComplete,
		AgentName: targetWorker,
		Timestamp: time.Now().UTC(),
		StatusMsg: fmt.Sprintf("Subtask %s completed successfully.", t.ID),
		Subtask: &gateway.SubtaskEventInfo{
			SubtaskID:   t.ID,
			Worker:      targetWorker,
			Description: t.Description,
			Status:      "COMPLETED",
			Output:      rawOutput,
			DurationMs:  durationMs,
		},
	}

	eventCh <- gateway.OutboundEvent{
		SessionID: sessionID,
		TurnID:    subtaskTurnID,
		Type:      gateway.EventStatusUpdate,
		AgentName: targetWorker,
		Timestamp: time.Now().UTC(),
		StatusMsg: fmt.Sprintf("Subtask %s completed successfully.", t.ID),
	}
	return ""
}

// IsSummarizerEnabled verifies whether the summarizer agent is active in configuration.
func (c *Controller) IsSummarizerEnabled() bool {
	cfgPath := c.agentsConfigPath
	if cfgPath == "" {
		cfgPath = "config/agents.json"
	}
	manifests, err := manifest.LoadActiveManifests(cfgPath, "")
	if err != nil {
		return false
	}
	_, enabled := manifests["summarizer"]
	return enabled
}

func (c *Controller) isSummarizerEnabled() bool {
	return c.IsSummarizerEnabled()
}

// BuildSummarizerPrompt constructs a concise synthesis prompt from executed subtask outputs.
func (c *Controller) BuildSummarizerPrompt(
	userGoal string,
	sched *scheduler.TaskScheduler,
	rawAccumulated string,
) string {
	var sb strings.Builder
	sb.WriteString("User Primary Goal:\n")
	sb.WriteString(userGoal)
	sb.WriteString("\n\nExecution Results:\n")

	subtasks := sched.GetSubtasks()
	if len(subtasks) > 0 {
		for _, st := range subtasks {
			sb.WriteString(fmt.Sprintf("- Subtask %s (@%s): %s\n", st.ID, st.GetWorker(), st.Description))
			sb.WriteString(fmt.Sprintf("  Status: %s\n", st.Status))
			if st.Output != "" {
				sb.WriteString(fmt.Sprintf("  Output: %s\n", st.Output))
			}
			if st.Error != "" {
				sb.WriteString(fmt.Sprintf("  Error: %s\n", st.Error))
			}
		}
	} else if strings.TrimSpace(rawAccumulated) != "" {
		sb.WriteString(rawAccumulated)
		sb.WriteString("\n")
	} else {
		sb.WriteString("Tasks executed successfully with no textual output.\n")
	}

	sb.WriteString("\nDirectives:\n")
	sb.WriteString("Synthesize the results above into a well-structured, clear, and human-readable final response. ")
	sb.WriteString("Directly answer the user's primary goal using clean markdown formatting (headings, bullet points, code blocks, or tables). ")
	sb.WriteString("Do not include conversational preamble, filler, or robotic apologies.")

	return sb.String()
}

// runSummarizer invokes the summarizer agent right before gateway delivery to produce structured output.
func (c *Controller) runSummarizer(
	ctx context.Context,
	turn TurnContext,
	sched *scheduler.TaskScheduler,
	rawAccumulated string,
	eventCh chan<- gateway.OutboundEvent,
) (string, error) {
	summaryPrompt := c.BuildSummarizerPrompt(turn.Prompt, sched, rawAccumulated)
	summaryTurnID := fmt.Sprintf("%s_summarizer", turn.TurnID)

	eventCh <- gateway.OutboundEvent{
		SessionID: turn.SessionID,
		TurnID:    summaryTurnID,
		TraceID:   turn.TraceID,
		Type:      gateway.EventStatusUpdate,
		AgentName: "summarizer",
		Timestamp: time.Now().UTC(),
		StatusMsg: "Synthesizing and formatting final output...",
	}

	summaryInput := TurnExecutionInput{
		SessionID: turn.SessionID,
		TurnID:    summaryTurnID,
		TraceID:   turn.TraceID,
		Decision: router.RouteDecision{
			Type:        router.RouteFastPath,
			TargetAgent: "summarizer",
			Prompt:      summaryPrompt,
		},
		Prompt:      summaryPrompt,
		History:     turn.History,
		Trigger:     turn.Trigger,
		AllowedCaps: turn.AllowedCapabilities,
	}

	summaryAccumulator := &stringAccumulator{}
	interceptorCh := make(chan gateway.OutboundEvent, 16)
	var forwardWg sync.WaitGroup
	forwardWg.Add(1)

	go func() {
		defer forwardWg.Done()
		for ev := range interceptorCh {
			if ev.TurnID == "" {
				ev.TurnID = summaryTurnID
			}
			if ev.AgentName == "" {
				ev.AgentName = "summarizer"
			}
			if ev.Type == gateway.EventTokenChunk && ev.TextDelta != "" {
				summaryAccumulator.WriteString(ev.TextDelta)
			}
			// Top-level turn completion is emitted by Orchestrate with telemetry metrics.
			if ev.Type == gateway.EventTurnComplete || ev.Type == gateway.EventTurnError {
				continue
			}
			eventCh <- ev
		}
	}()

	err := c.executor.Execute(ctx, summaryInput, interceptorCh)
	close(interceptorCh)
	forwardWg.Wait()

	if err != nil {
		return "", err
	}
	return summaryAccumulator.String(), nil
}

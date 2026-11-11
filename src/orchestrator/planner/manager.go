package planner

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

// LLMCaller defines the interface required by the Manager Agent to perform cognitive reasoning.
type LLMCaller interface {
	Generate(ctx context.Context, systemPrompt, userPrompt string) (string, error)
}

// ManagerAgent is the SOLE agent residing in Layer 2, responsible strictly for planning and task decomposition.
type ManagerAgent struct {
	workers        []WorkerCapability
	llm            LLMCaller
	promptFilePath string
}

// NewManagerAgent constructs the Layer 2 Manager Agent.
func NewManagerAgent(llm LLMCaller, workers []WorkerCapability, promptFilePath string) *ManagerAgent {
	if len(workers) == 0 {
		workers = DiscoverAndLoadActiveWorkers("", "")
	}
	if llm == nil {
		bridge := NewPythonManagerBridge("", "")
		if bridge.pythonBinary != "" {
			llm = bridge
		}
	}
	return &ManagerAgent{
		workers:        workers,
		llm:            llm,
		promptFilePath: promptFilePath,
	}
}

// Plan decomposes a primary user goal into an actionable TaskPlan DAG.
func (m *ManagerAgent) Plan(ctx context.Context, goal string, contextData map[string]interface{}) (*TaskPlan, error) {
	goal = strings.TrimSpace(goal)
	if goal == "" {
		return nil, errors.New("cannot plan with an empty goal")
	}

	// Deterministic fallback if no LLM caller or runtime is attached
	if m.llm == nil {
		return m.generateFallbackPlan(goal), nil
	}

	// Direct delegation if attached caller is the Python Manager Bridge
	if bridge, ok := m.llm.(*PythonManagerBridge); ok {
		plan, err := bridge.Plan(ctx, goal, contextData)
		if err == nil {
			m.validateAndNormalizePlan(plan, goal)
			return plan, nil
		}
	}

	sysPrompt := BuildPlannerSystemPrompt(m.workers, m.promptFilePath)
	userPrompt := fmt.Sprintf("User Request: %s", goal)
	if len(contextData) > 0 {
		ctxBytes, _ := json.Marshal(contextData)
		userPrompt = fmt.Sprintf("Context: %s\n\n%s", string(ctxBytes), userPrompt)
	}

	rawOutput, err := m.llm.Generate(ctx, sysPrompt, userPrompt)
	if err != nil {
		return m.generateFallbackPlan(goal), fmt.Errorf("manager planning failed: %w", err)
	}

	cleanJSON := extractJSON(rawOutput)
	var plan TaskPlan
	if err := json.Unmarshal([]byte(cleanJSON), &plan); err != nil {
		return m.generateFallbackPlan(goal), nil
	}

	m.validateAndNormalizePlan(&plan, goal)
	return &plan, nil
}

func (m *ManagerAgent) validateAndNormalizePlan(plan *TaskPlan, originalGoal string) {
	if plan.PlanID == "" {
		plan.PlanID = fmt.Sprintf("plan_%s", uuid.New().String()[:12])
	}
	if plan.PrimaryGoal == "" {
		plan.PrimaryGoal = originalGoal
	}

	knownWorkers := make(map[string]bool)
	for _, w := range m.workers {
		knownWorkers[strings.ToLower(w.Name)] = true
	}

	for i := range plan.SubTasks {
		st := &plan.SubTasks[i]
		if st.ID == "" {
			st.ID = fmt.Sprintf("task_%d", i+1)
		}

		targetWorker := strings.ToLower(strings.TrimSpace(st.GetWorker()))
		if !knownWorkers[targetWorker] {
			targetWorker = "system"
		}
		st.AssignedWorker = targetWorker
		st.AssignedAgent = targetWorker
		st.Status = StatusPending
		if st.DependsOn == nil {
			st.DependsOn = []string{}
		}
		if st.ConfidenceScore == 0 {
			st.ConfidenceScore = 1.0
		}
	}
}

func (m *ManagerAgent) generateFallbackPlan(goal string) *TaskPlan {
	return &TaskPlan{
		PlanID:      fmt.Sprintf("plan_fallback_%d", time.Now().UnixMilli()),
		PrimaryGoal: goal,
		SubTasks: []SubTask{
			{
				ID:              "task_1",
				Description:     goal,
				AssignedWorker:  "system",
				AssignedAgent:   "system",
				DependsOn:       []string{},
				Status:          StatusPending,
				ConfidenceScore: 1.0,
			},
		},
	}
}

// extractJSON extracts the pure JSON payload between the first '{' and the last '}'.
func extractJSON(s string) string {
	s = strings.TrimSpace(s)
	// Remove markdown backticks if the model added them despite instructions
	if strings.HasPrefix(s, "```") {
		lines := strings.Split(s, "\n")
		if len(lines) >= 2 {
			lines = lines[1:]
			if len(lines) > 0 && strings.HasPrefix(lines[len(lines)-1], "```") {
				lines = lines[:len(lines)-1]
			}
			s = strings.Join(lines, "\n")
		}
	}
	s = strings.TrimSpace(s)

	start := strings.Index(s, "{")
	end := strings.LastIndex(s, "}")
	if start != -1 && end != -1 && end > start {
		return s[start : end+1]
	}
	return s
}

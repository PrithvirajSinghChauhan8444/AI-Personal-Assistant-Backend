package planner

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"assistant/src/orchestrator/session"

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
	if workers == nil {
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
func (m *ManagerAgent) Plan(ctx context.Context, goal string, contextData map[string]interface{}, history ...[]session.ChatMessage) (*TaskPlan, error) {
	goal = strings.TrimSpace(goal)
	if goal == "" {
		return nil, errors.New("cannot plan with an empty goal")
	}

	if len(m.workers) == 0 {
		return nil, errors.New("cannot plan tasks: no specialist worker agents are currently enabled in config/agents.json. Please enable the required workers in config/agents.json to proceed")
	}

	if m.llm == nil {
		return nil, errors.New("manager planner has no LLM caller or bridge attached")
	}

	var chatHistory []session.ChatMessage
	if len(history) > 0 {
		chatHistory = history[0]
	}

	// Direct delegation if attached caller is the Python Manager Bridge
	if bridge, ok := m.llm.(*PythonManagerBridge); ok {
		plan, err := bridge.Plan(ctx, goal, contextData, chatHistory)
		if err == nil {
			if normErr := m.validateAndNormalizePlan(plan, goal); normErr != nil {
				return nil, normErr
			}
			return plan, nil
		}
	}

	sysPrompt := BuildPlannerSystemPrompt(m.workers, m.promptFilePath)
	userPrompt := fmt.Sprintf("User Request: %s", goal)
	if len(chatHistory) > 0 {
		var histBuilder strings.Builder
		histBuilder.WriteString("Conversation History:\n")
		startIdx := 0
		if len(chatHistory) > 10 {
			startIdx = len(chatHistory) - 10
		}
		for _, msg := range chatHistory[startIdx:] {
			histBuilder.WriteString(fmt.Sprintf("%s: %s\n", msg.Role, msg.Content))
		}
		userPrompt = fmt.Sprintf("%s\n\n%s", histBuilder.String(), userPrompt)
	}
	if len(contextData) > 0 {
		ctxBytes, _ := json.Marshal(contextData)
		userPrompt = fmt.Sprintf("Context: %s\n\n%s", string(ctxBytes), userPrompt)
	}

	rawOutput, err := m.llm.Generate(ctx, sysPrompt, userPrompt)
	if err != nil {
		return nil, fmt.Errorf("manager planning failed: %w", err)
	}

	cleanJSON := extractJSON(rawOutput)
	var plan TaskPlan
	if err := json.Unmarshal([]byte(cleanJSON), &plan); err != nil {
		return nil, fmt.Errorf("failed to parse manager plan JSON: %w (raw output: %s)", err, rawOutput)
	}

	if normErr := m.validateAndNormalizePlan(&plan, goal); normErr != nil {
		return nil, normErr
	}
	return &plan, nil
}

func (m *ManagerAgent) validateAndNormalizePlan(plan *TaskPlan, originalGoal string) error {
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

	if len(plan.SubTasks) == 0 {
		return errors.New("no subtasks could be scheduled: required capabilities are disabled or missing from enabled workers in config/agents.json")
	}

	for i := range plan.SubTasks {
		st := &plan.SubTasks[i]
		if st.ID == "" {
			st.ID = fmt.Sprintf("task_%d", i+1)
		}

		targetWorker := strings.ToLower(strings.TrimSpace(st.GetWorker()))
		if targetWorker == "" || !knownWorkers[targetWorker] {
			return fmt.Errorf("task %q cannot be scheduled: worker %q is disabled or does not exist in config/agents.json", st.ID, targetWorker)
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
	return nil
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

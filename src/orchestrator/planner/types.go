package planner

// SubTaskStatus represents the lifecycle state of an individual step in the DAG.
type SubTaskStatus string

const (
	StatusPending    SubTaskStatus = "PENDING"
	StatusInProgress SubTaskStatus = "IN_PROGRESS"
	StatusCompleted  SubTaskStatus = "COMPLETED"
	StatusFailed     SubTaskStatus = "FAILED"
	StatusAborted    SubTaskStatus = "ABORTED"
)

// SubTask represents an atomic unit of execution assigned to a specialist worker.
type SubTask struct {
	ID               string                 `json:"id"`
	Description      string                 `json:"description"`
	AssignedWorker   string                 `json:"assigned_worker"`
	AssignedAgent    string                 `json:"assigned_agent,omitempty"` // Alias support
	DependsOn        []string               `json:"depends_on"`
	ConfidenceScore  float64                `json:"confidence_score,omitempty"`
	ConfidenceReason string                 `json:"confidence_reason,omitempty"`
	EntityReference  *string                `json:"entity_reference,omitempty"`
	InputContext     map[string]interface{} `json:"input_context,omitempty"`
	Status           SubTaskStatus          `json:"status"`
	Output           string                 `json:"output,omitempty"`
	Error            string                 `json:"error,omitempty"`
}

// GetWorker returns the canonical target worker name.
func (st *SubTask) GetWorker() string {
	if st.AssignedWorker != "" {
		return st.AssignedWorker
	}
	return st.AssignedAgent
}

// TaskPlan represents the full execution plan DAG produced by the Manager Agent.
type TaskPlan struct {
	PlanID      string    `json:"plan_id,omitempty"`
	PrimaryGoal string    `json:"primary_goal"`
	SubTasks    []SubTask `json:"subtasks"`
}

// WorkerCapability describes an external specialist worker available for task assignment.
type WorkerCapability struct {
	Name         string   `json:"name"`
	Description  string   `json:"description"`
	RoutingRules []string `json:"routing_rules,omitempty"`
}

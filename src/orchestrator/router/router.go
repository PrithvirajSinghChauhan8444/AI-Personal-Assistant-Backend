package router

import (
	"strings"

	"assistant/src/gateway"
)

// RouteType distinguishes between direct single-agent execution and cognitive manager planning.
type RouteType string

const (
	// RouteFastPath directly addresses a specialized worker agent without manager overhead.
	RouteFastPath RouteType = "FAST_PATH"
	// RouteManager routes to the cognitive manager agent for decomposition and multi-agent coordination.
	RouteManager RouteType = "MANAGER"
)

// RouteDecision contains the execution destination for an incoming turn.
type RouteDecision struct {
	Type        RouteType `json:"type"`
	TargetAgent string    `json:"target_agent"`
	Prompt      string    `json:"prompt"`
}

// KnownAgentAliases maps shorthand or legacy agent names to canonical personas.
var KnownAgentAliases = map[string]string{
	"sys":          "system",
	"system":       "system",
	"sh":           "system",
	"bash":         "system",
	"browser":      "browser",
	"web":          "browser",
	"research":     "research",
	"search":       "research",
	"productivity": "productivity",
	"prod":         "productivity",
	"mail":         "productivity",
	"gmail":        "productivity",
	"calendar":     "productivity",
}

// TaskRouter determines whether an inbound request follows the direct fast-path or manager coordination.
type TaskRouter struct{}

// NewTaskRouter constructs a TaskRouter.
func NewTaskRouter() *TaskRouter {
	return &TaskRouter{}
}

// Resolve analyzes the InboundTurnRequest and resolves the execution target.
func (r *TaskRouter) Resolve(req gateway.InboundTurnRequest) RouteDecision {
	target := strings.ToLower(strings.TrimSpace(req.TargetAgent))

	// If explicit agent is requested and recognized, use direct fast-path
	if canonicalAgent, exists := KnownAgentAliases[target]; exists {
		return RouteDecision{
			Type:        RouteFastPath,
			TargetAgent: canonicalAgent,
			Prompt:      req.Prompt,
		}
	}

	// Default: Unrouted or "auto" queries are handled by the Manager Agent
	return RouteDecision{
		Type:        RouteManager,
		TargetAgent: "manager",
		Prompt:      req.Prompt,
	}
}

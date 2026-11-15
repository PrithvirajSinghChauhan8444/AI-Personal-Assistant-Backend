package router

import (
	"strings"

	"assistant/src/gateway"
	"assistant/src/orchestrator/manifest"
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
	"memory":       "memory",
	"mem":          "memory",
}

// TaskRouter determines whether an inbound request follows the direct fast-path or manager coordination.
type TaskRouter struct {
	aliases map[string]string
}

// NewTaskRouter constructs a TaskRouter auto-registering aliases from manifests with static fallback.
func NewTaskRouter() *TaskRouter {
	return NewTaskRouterWithConfig("config/agents.json", "src/agents")
}

// NewTaskRouterWithConfig constructs a TaskRouter from explicit config and agent paths.
func NewTaskRouterWithConfig(configPath, agentsDir string) *TaskRouter {
	aliasMap := make(map[string]string)

	manifests, err := manifest.LoadActiveManifests(configPath, agentsDir)
	if err == nil {
		for id, m := range manifests {
			canonical := strings.ToLower(id)
			aliasMap[canonical] = canonical
			for _, alias := range m.AgentAliases {
				cleanAlias := strings.ToLower(strings.TrimSpace(alias))
				if cleanAlias != "" {
					aliasMap[cleanAlias] = canonical
				}
			}
		}
		// Map static KnownAgentAliases only if the target worker is active in manifests
		for k, v := range KnownAgentAliases {
			canonical := strings.ToLower(v)
			if _, isActive := manifests[canonical]; isActive {
				aliasMap[strings.ToLower(k)] = canonical
			}
		}
	} else {
		for k, v := range KnownAgentAliases {
			aliasMap[strings.ToLower(k)] = strings.ToLower(v)
		}
	}

	return &TaskRouter{aliases: aliasMap}
}

// Resolve analyzes the InboundTurnRequest and resolves the execution target.
func (r *TaskRouter) Resolve(req gateway.InboundTurnRequest) RouteDecision {
	target := strings.ToLower(strings.TrimSpace(req.TargetAgent))

	aliasMap := r.aliases
	if aliasMap == nil {
		aliasMap = KnownAgentAliases
	}

	// If explicit agent is requested and recognized, use direct fast-path
	if canonicalAgent, exists := aliasMap[target]; exists {
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

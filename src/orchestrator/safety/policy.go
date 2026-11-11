package safety

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"assistant/src/gateway"
)

// RiskLevel defines the risk tier of a system or external action.
type RiskLevel string

const (
	RiskLow    RiskLevel = "LOW"    // Read-only tools (fs_read, net_fetch, git_status, gmail_list)
	RiskMedium RiskLevel = "MEDIUM" // Modifying non-critical files, draft creation (fs_write, draft)
	RiskHigh   RiskLevel = "HIGH"   // Destructive tools (fs_delete, sys_exec, sys_kill, git_commit)
)

// ToolPolicy defines execution permissions and risk constraints for a single tool.
type ToolPolicy struct {
	ToolName            string    `json:"tool_name"`
	Risk                RiskLevel `json:"risk"`
	RequiresInteractive bool      `json:"requires_interactive"` // If true, forbidden in AUTONOMOUS mode
	RequiredCapability  string    `json:"required_capability"`  // Matches gateway.AllowedCapabilities
}

// EvaluationResult contains the safety verdict for a tool invocation.
type EvaluationResult struct {
	Allowed      bool      `json:"allowed"`
	RequiresHITL bool      `json:"requires_hitl"`
	Risk         RiskLevel `json:"risk"`
	Reason       string    `json:"reason"`
}

// Gatekeeper verifies tool action requests against safety policies and trigger modes.
type Gatekeeper struct {
	policies map[string]ToolPolicy
}

// NewGatekeeper initializes a Gatekeeper populated with default standard tool policies.
func NewGatekeeper() *Gatekeeper {
	gk := &Gatekeeper{
		policies: make(map[string]ToolPolicy),
	}
	gk.registerDefaults()
	return gk
}

// RegisterPolicy registers or overrides a policy for a specific tool.
func (g *Gatekeeper) RegisterPolicy(policy ToolPolicy) {
	g.policies[strings.ToLower(policy.ToolName)] = policy
}

type safetyPolicyConfigFile struct {
	DefaultUnknownToolRisk RiskLevel    `json:"default_unknown_tool_risk"`
	Tools                  []ToolPolicy `json:"tools"`
}

// LoadPoliciesFromFile loads and overrides tool safety policies from a JSON configuration file.
func (g *Gatekeeper) LoadPoliciesFromFile(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("failed to read policy config %q: %w", path, err)
	}

	var cfg safetyPolicyConfigFile
	if err := json.Unmarshal(data, &cfg); err != nil {
		return fmt.Errorf("failed to parse policy config %q: %w", path, err)
	}

	for _, p := range cfg.Tools {
		g.RegisterPolicy(p)
	}
	return nil
}

// Evaluate evaluates whether a tool is permitted to run under the active session constraints.
func (g *Gatekeeper) Evaluate(toolName string, trigger gateway.TriggerType, allowedCapabilities []string) EvaluationResult {
	canonicalName := strings.ToLower(strings.TrimSpace(toolName))
	policy, found := g.policies[canonicalName]

	// Unknown tools default conservatively to high risk requiring interactive human presence
	if !found {
		policy = ToolPolicy{
			ToolName:            canonicalName,
			Risk:                RiskHigh,
			RequiresInteractive: true,
			RequiredCapability:  "system_exec",
		}
	}

	// Rule 1: Check autonomous mode restriction
	if trigger == gateway.TriggerAutonomous && policy.RequiresInteractive {
		return EvaluationResult{
			Allowed:      false,
			RequiresHITL: false,
			Risk:         policy.Risk,
			Reason:       fmt.Sprintf("tool %q requires interactive user mode and is forbidden in autonomous trigger mode", toolName),
		}
	}

	// Rule 2: Check required capability scope (if capabilities are specified)
	if policy.RequiredCapability != "" && len(allowedCapabilities) > 0 {
		if !hasCapability(allowedCapabilities, policy.RequiredCapability) {
			return EvaluationResult{
				Allowed:      false,
				RequiresHITL: false,
				Risk:         policy.Risk,
				Reason:       fmt.Sprintf("tool %q requires capability %q which is not granted in allowed scope", toolName, policy.RequiredCapability),
			}
		}
	}

	// Rule 3: High risk tools in interactive mode require Human-In-The-Loop clearance
	if policy.Risk == RiskHigh {
		return EvaluationResult{
			Allowed:      true,
			RequiresHITL: true,
			Risk:         RiskHigh,
			Reason:       fmt.Sprintf("tool %q is classified as HIGH risk and requires user approval", toolName),
		}
	}

	// Safe to execute immediately
	return EvaluationResult{
		Allowed:      true,
		RequiresHITL: false,
		Risk:         policy.Risk,
		Reason:       "action conforms to safety policies",
	}
}

func (g *Gatekeeper) registerDefaults() {
	// Low Risk (Read-only)
	lowRiskTools := []struct {
		name string
		cap  string
	}{
		{"fs_read", "fs_read"},
		{"fs_list", "fs_read"},
		{"fs_ripgrep", "fs_read"},
		{"git_status", "git"},
		{"git_diff", "git"},
		{"net_search", "network"},
		{"net_fetch", "network"},
		{"gmail_list", "email"},
		{"gmail_read", "email"},
		{"calendar_list", "calendar"},
		{"memory_search", "memory"},
	}
	for _, t := range lowRiskTools {
		g.RegisterPolicy(ToolPolicy{
			ToolName:            t.name,
			Risk:                RiskLow,
			RequiresInteractive: false,
			RequiredCapability:  t.cap,
		})
	}

	// Medium Risk (Non-destructive modifications)
	mediumRiskTools := []struct {
		name string
		cap  string
	}{
		{"fs_write", "fs_write"},
		{"gmail_send_draft", "email"},
		{"memory_store_fact", "memory"},
		{"memory_update_profile", "memory"},
	}
	for _, t := range mediumRiskTools {
		g.RegisterPolicy(ToolPolicy{
			ToolName:            t.name,
			Risk:                RiskMedium,
			RequiresInteractive: false,
			RequiredCapability:  t.cap,
		})
	}

	// Standard specialist worker agents
	workerAgents := []struct {
		name string
		cap  string
	}{
		{"system", "system"},
		{"browser", "browser"},
		{"research", "research"},
		{"productivity", "productivity"},
		{"manager", "manager"},
	}
	for _, w := range workerAgents {
		g.RegisterPolicy(ToolPolicy{
			ToolName:            w.name,
			Risk:                RiskLow,
			RequiresInteractive: false,
			RequiredCapability:  w.cap,
		})
	}

	// High Risk (Destructive actions & shell execution)
	highRiskTools := []struct {
		name string
		cap  string
	}{
		{"sys_exec", "system_exec"},
		{"sys_kill", "system_kill"},
		{"fs_delete", "fs_delete"},
		{"git_commit", "git"},
		{"git_push", "git"},
		{"memory_delete", "memory"},
	}
	for _, t := range highRiskTools {
		g.RegisterPolicy(ToolPolicy{
			ToolName:            t.name,
			Risk:                RiskHigh,
			RequiresInteractive: true,
			RequiredCapability:  t.cap,
		})
	}
}

func hasCapability(caps []string, required string) bool {
	for _, c := range caps {
		if c == "*" || strings.EqualFold(c, required) {
			return true
		}
	}
	return false
}

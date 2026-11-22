package manifest

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// ToolSpec represents a declared tool contract within an agent manifest.
type ToolSpec struct {
	Name               string `json:"name"`
	Description        string `json:"description"`
	Risk               string `json:"risk"`
	ExecutionDomain    string `json:"execution_domain"`
	RequiredCapability string `json:"required_capability"`
}

// ModelSpec defines default LLM model configuration for an agent.
type ModelSpec struct {
	Default     string  `json:"default"`
	Temperature float64 `json:"temperature"`
}

// AgentManifest represents a self-contained specialist agent identity and specification.
type AgentManifest struct {
	AgentIdentifier    string     `json:"agent_identifier"`
	DisplayName        string     `json:"display_name"`
	Version            string     `json:"version"`
	AgentAliases       []string   `json:"agent_aliases"`
	FallbackCapability string     `json:"fallback_capability"`
	Model              ModelSpec  `json:"model"`
	Description        string     `json:"description"`
	RoutingRules       []string   `json:"routing_rules"`
	Tools              []ToolSpec `json:"tools"`
}

// AgentControlEntry represents an operational toggle entry in config/agents.json.
type AgentControlEntry struct {
	Enabled      *bool                  `json:"enabled"`
	ConfigPath   string                 `json:"config_path"`
	ManifestPath string                 `json:"manifest_path"`
	Model        string                 `json:"model,omitempty"`
	Temperature  *float64               `json:"temperature,omitempty"`
	Description  string                 `json:"description,omitempty"`
	RoutingRules []string               `json:"routing_rules,omitempty"`
	Overrides    map[string]interface{} `json:"-"`
}

// UnmarshalJSON implements custom deserialization for AgentControlEntry,
// gracefully supporting model_override as string, dict, or null.
func (e *AgentControlEntry) UnmarshalJSON(data []byte) error {
	type rawEntry AgentControlEntry
	var shadow struct {
		rawEntry
		RawOverride json.RawMessage `json:"model_override,omitempty"`
	}

	if err := json.Unmarshal(data, &shadow); err != nil {
		return err
	}

	*e = AgentControlEntry(shadow.rawEntry)
	e.Overrides = parseModelOverride(shadow.RawOverride)
	return nil
}

func parseModelOverride(raw json.RawMessage) map[string]interface{} {
	if len(raw) == 0 || string(raw) == "null" {
		return nil
	}
	var strVal string
	if err := json.Unmarshal(raw, &strVal); err == nil {
		if strVal == "" {
			return nil
		}
		return map[string]interface{}{"model": strVal}
	}
	var mapVal map[string]interface{}
	if err := json.Unmarshal(raw, &mapVal); err == nil {
		return mapVal
	}
	return nil
}

// MarshalJSON preserves custom serialization format for AgentControlEntry.
func (e AgentControlEntry) MarshalJSON() ([]byte, error) {
	type rawEntry AgentControlEntry
	shadow := struct {
		rawEntry
		ModelOverride interface{} `json:"model_override,omitempty"`
	}{
		rawEntry:      rawEntry(e),
		ModelOverride: e.Overrides,
	}
	return json.Marshal(shadow)
}

// capitalize returns the string with its first rune in uppercase.
func capitalize(s string) string {
	if len(s) == 0 {
		return ""
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

// FindAgentConfigFile searches agentDir for standard config files (<name>_config.json, manifest.json, agent.json).
func FindAgentConfigFile(agentDir, agentName string) string {
	cleanName := strings.ToLower(agentName)
	candidates := []string{
		filepath.Join(agentDir, fmt.Sprintf("%s_config.json", cleanName)),
		filepath.Join(agentDir, "manifest.json"),
		filepath.Join(agentDir, "agent.json"),
	}
	for _, cand := range candidates {
		if _, err := os.Stat(cand); err == nil {
			return cand
		}
	}
	return ""
}

// LoadManifest reads and parses a single agent manifest JSON file.
func LoadManifest(path string) (*AgentManifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read manifest %q: %w", path, err)
	}

	var m AgentManifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("failed to parse manifest JSON %q: %w", path, err)
	}

	if m.AgentIdentifier == "" {
		// Infer from directory name if not explicit
		dir := filepath.Base(filepath.Dir(path))
		m.AgentIdentifier = strings.ToLower(dir)
	}

	return &m, nil
}

// SyncControlRegistry scans agentsDir for specialist agents and auto-registers new ones into configPath with enabled: false.
func SyncControlRegistry(configPath, agentsDir string) error {
	if configPath == "" {
		configPath = filepath.Join("config", "agents.json")
	}
	if agentsDir == "" {
		agentsDir = filepath.Join("src", "agents")
	}

	var rawData map[string]interface{}
	content, err := os.ReadFile(configPath)
	if err == nil && len(strings.TrimSpace(string(content))) > 0 {
		if unmarshalErr := json.Unmarshal(content, &rawData); unmarshalErr != nil {
			return fmt.Errorf("aborted sync to prevent data loss, malformed JSON in %q: %w", configPath, unmarshalErr)
		}
	}
	if rawData == nil {
		rawData = make(map[string]interface{})
	}

	entries, err := os.ReadDir(agentsDir)
	if err != nil {
		return fmt.Errorf("failed to read agents directory %q: %w", agentsDir, err)
	}

	changed := false

	// Ensure Manager agent entry is always present and enabled
	if _, exists := rawData["manager"]; !exists {
		rawData["manager"] = map[string]interface{}{
			"enabled":              true,
			"model":                "google:gemini-3.5-flash-lite",
			"temperature":          0.1,
			"max_parallel_workers": 4,
			"auto_heal_deadlocks":  true,
			"description":          "Layer 2 Cognitive Planner that decomposes user requests into actionable DAG task plans.",
		}
		changed = true
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		name := strings.ToLower(entry.Name())
		if name == "manager" || name == "engine" || strings.HasPrefix(name, ".") || strings.HasPrefix(name, "_") {
			continue
		}

		foundConfigPath := FindAgentConfigFile(filepath.Join(agentsDir, entry.Name()), name)
		if foundConfigPath == "" {
			continue
		}

		if _, exists := rawData[name]; !exists {
			rawData[name] = map[string]interface{}{
				"enabled":        false,
				"config_path":    filepath.ToSlash(foundConfigPath),
				"model_override": nil,
			}
			changed = true
		}
	}

	if changed {
		updated, marshalErr := json.MarshalIndent(rawData, "", "  ")
		if marshalErr != nil {
			return fmt.Errorf("failed to format updated agents registry: %w", marshalErr)
		}
		updated = append(updated, '\n')
		if writeErr := os.WriteFile(configPath, updated, 0644); writeErr != nil {
			return fmt.Errorf("failed to write updated agents registry %q: %w", configPath, writeErr)
		}
	}

	return nil
}

// ResolvePath searches for path candidates across current directory and parent directories.
func ResolvePath(path string) string {
	if _, err := os.Stat(path); err == nil {
		return path
	}
	candidates := []string{
		filepath.Join("..", path),
		filepath.Join("..", "..", path),
		filepath.Join("..", "..", "..", path),
		filepath.Join("..", "..", "..", "..", path),
		filepath.Join("..", "..", "..", "..", "..", path),
	}
	for _, cand := range candidates {
		if _, err := os.Stat(cand); err == nil {
			return cand
		}
	}
	return path
}

// LoadActiveManifests loads all manifests for active/enabled agents according to config/agents.json.
func LoadActiveManifests(configPath, agentsDir string) (map[string]*AgentManifest, error) {
	if configPath == "" {
		configPath = "config/agents.json"
	}
	configPath = ResolvePath(configPath)

	if agentsDir == "" {
		agentsDir = "src/agents"
	}
	agentsDir = ResolvePath(agentsDir)

	manifests := make(map[string]*AgentManifest)

	data, err := os.ReadFile(configPath)
	if err != nil {
		return manifests, fmt.Errorf("failed to read control registry %q: %w", configPath, err)
	}

	var registry map[string]AgentControlEntry
	if len(strings.TrimSpace(string(data))) > 0 {
		if err := json.Unmarshal(data, &registry); err != nil {
			return manifests, fmt.Errorf("failed to parse control registry %q: %w", configPath, err)
		}
	}

	for rawName, entry := range registry {
		name := strings.ToLower(rawName)
		if name == "manager" {
			continue
		}
		if entry.Enabled != nil && !*entry.Enabled {
			continue
		}

		targetConfigPath := entry.ConfigPath
		if targetConfigPath == "" {
			targetConfigPath = entry.ManifestPath
		}
		if targetConfigPath == "" {
			targetConfigPath = FindAgentConfigFile(filepath.Join(agentsDir, name), name)
			if targetConfigPath == "" {
				targetConfigPath = filepath.Join(agentsDir, name, fmt.Sprintf("%s_config.json", name))
			}
		}

		m, loadErr := LoadManifest(targetConfigPath)
		if loadErr == nil && m != nil {
			id := strings.ToLower(m.AgentIdentifier)
			manifests[id] = m
		} else {
			// Backward compatibility fallback: construct synthetic manifest from config entry
			desc := entry.Description
			if desc == "" {
				desc = fmt.Sprintf("Specialist worker in %s operations.", name)
			}
			rules := entry.RoutingRules
			if len(rules) == 0 {
				rules = []string{fmt.Sprintf("Assign for tasks relating to %s.", name)}
			}
			manifests[name] = &AgentManifest{
				AgentIdentifier:    name,
				DisplayName:        capitalize(name) + " Agent",
				Version:            "1.0.0",
				AgentAliases:       []string{name},
				FallbackCapability: "system",
				Description:        desc,
				RoutingRules:       rules,
			}
		}
	}

	return manifests, nil
}

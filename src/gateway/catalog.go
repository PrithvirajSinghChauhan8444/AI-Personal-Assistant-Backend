package gateway

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"assistant/src/orchestrator/manifest"
)

var (
	// ErrCannotDisableManager is returned when attempting to disable the core manager agent.
	ErrCannotDisableManager = errors.New("cannot disable manager: manager is a protected core agent")
	// ErrAgentNotFound is returned when an agent is not registered in config/agents.json.
	ErrAgentNotFound = errors.New("agent not found in catalog")
)

var catalogMu sync.Mutex

// GetAgentCatalog reads config/agents.json and agent manifests to construct a runtime catalog snapshot.
func (g *Gateway) GetAgentCatalog() (*AgentCatalogSnapshot, error) {
	catalogMu.Lock()
	defer catalogMu.Unlock()

	cfgPath := manifest.ResolvePath("config/agents.json")
	agentsDir := manifest.ResolvePath("src/agents")

	data, err := os.ReadFile(cfgPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read agents configuration %q: %w", cfgPath, err)
	}

	var rawRegistry map[string]map[string]interface{}
	if err := json.Unmarshal(data, &rawRegistry); err != nil {
		return nil, fmt.Errorf("failed to parse agents configuration: %w", err)
	}

	snapshot := &AgentCatalogSnapshot{
		TotalAgents: len(rawRegistry),
		Agents:      make(map[string]AgentStatusInfo),
	}

	for id, cfg := range rawRegistry {
		cleanID := strings.ToLower(id)
		enabled := true
		if val, ok := cfg["enabled"].(bool); ok {
			enabled = val
		}

		if enabled {
			snapshot.ActiveAgents++
		} else {
			snapshot.DisabledAgents++
		}

		isCore := cleanID == "manager"
		displayName := strings.ToUpper(cleanID[:1]) + cleanID[1:]
		assignedModel := "default"
		if m, ok := cfg["model"].(string); ok && m != "" {
			assignedModel = m
		}

		var modelOverride *string
		if mo, ok := cfg["model_override"].(string); ok && mo != "" {
			modelOverride = &mo
			assignedModel = mo
		}

		cfgPathStr := ""
		if cp, ok := cfg["config_path"].(string); ok {
			cfgPathStr = cp
		}

		var capabilities []string
		var declaredTools []string

		// Discover manifest details if available
		agentFolder := filepath.Join(agentsDir, cleanID)
		manifestPath := manifest.FindAgentConfigFile(agentFolder, cleanID)
		if manifestPath != "" {
			if m, err := manifest.LoadManifest(manifestPath); err == nil && m != nil {
				if m.DisplayName != "" {
					displayName = m.DisplayName
				}
				if m.Model.Default != "" && modelOverride == nil && assignedModel == "default" {
					assignedModel = m.Model.Default
				}
				capabilities = append(capabilities, m.AgentAliases...)
				capabilities = append(capabilities, m.RoutingRules...)
				for _, t := range m.Tools {
					declaredTools = append(declaredTools, t.Name)
				}
			}
		}

		snapshot.Agents[cleanID] = AgentStatusInfo{
			Identifier:    cleanID,
			DisplayName:   displayName,
			Enabled:       enabled,
			IsCore:        isCore,
			AssignedModel: assignedModel,
			ModelOverride: modelOverride,
			Capabilities:  capabilities,
			DeclaredTools: declaredTools,
			ConfigPath:    cfgPathStr,
		}
	}

	return snapshot, nil
}

// SetAgentStatus enables or disables a specialist agent and persists the update atomically.
func (g *Gateway) SetAgentStatus(agentID string, enabled bool) error {
	cleanID := strings.ToLower(strings.TrimSpace(agentID))
	if cleanID == "manager" && !enabled {
		return ErrCannotDisableManager
	}

	catalogMu.Lock()
	defer catalogMu.Unlock()

	cfgPath := manifest.ResolvePath("config/agents.json")
	data, err := os.ReadFile(cfgPath)
	if err != nil {
		return fmt.Errorf("failed to read agents configuration %q: %w", cfgPath, err)
	}

	var rawRegistry map[string]map[string]interface{}
	if err := json.Unmarshal(data, &rawRegistry); err != nil {
		return fmt.Errorf("failed to parse agents configuration: %w", err)
	}

	entry, exists := rawRegistry[cleanID]
	if !exists {
		return ErrAgentNotFound
	}

	entry["enabled"] = enabled
	rawRegistry[cleanID] = entry

	if err := writeAtomicJSON(cfgPath, rawRegistry); err != nil {
		return err
	}

	// Broadcast status change event to observers
	if g.hub != nil {
		g.hub.ProcessEvent(context.Background(), OutboundEvent{
			Type:      EventAgentStatusChanged,
			AgentName: cleanID,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Agent %q status changed to enabled=%v", cleanID, enabled),
		})
	}

	return nil
}

// UpdateAgentConfig modifies runtime parameters such as model override or temperature.
func (g *Gateway) UpdateAgentConfig(agentID string, update AgentConfigUpdate) error {
	cleanID := strings.ToLower(strings.TrimSpace(agentID))

	catalogMu.Lock()
	defer catalogMu.Unlock()

	cfgPath := manifest.ResolvePath("config/agents.json")
	data, err := os.ReadFile(cfgPath)
	if err != nil {
		return fmt.Errorf("failed to read agents configuration %q: %w", cfgPath, err)
	}

	var rawRegistry map[string]map[string]interface{}
	if err := json.Unmarshal(data, &rawRegistry); err != nil {
		return fmt.Errorf("failed to parse agents configuration: %w", err)
	}

	entry, exists := rawRegistry[cleanID]
	if !exists {
		return ErrAgentNotFound
	}

	if update.ModelOverride != nil {
		if cleanID == "manager" {
			entry["model"] = *update.ModelOverride
		} else {
			entry["model_override"] = *update.ModelOverride
		}
	}

	if update.Temperature != nil {
		entry["temperature"] = *update.Temperature
	}

	if update.MaxIterations != nil {
		entry["max_iterations"] = *update.MaxIterations
	}

	rawRegistry[cleanID] = entry

	if err := writeAtomicJSON(cfgPath, rawRegistry); err != nil {
		return err
	}

	if g.hub != nil {
		g.hub.ProcessEvent(context.Background(), OutboundEvent{
			Type:      EventStatusUpdate,
			AgentName: cleanID,
			Timestamp: time.Now().UTC(),
			StatusMsg: fmt.Sprintf("Agent %q configuration updated", cleanID),
		})
	}

	return nil
}

// UpdateAgentModel modifies the assigned model for a specific agent in config/agents.json.
func (g *Gateway) UpdateAgentModel(agentID string, modelName string) error {
	cleanModel := strings.TrimSpace(modelName)
	if cleanModel == "" {
		return errors.New("model name cannot be empty")
	}
	if !strings.Contains(cleanModel, ":") {
		cleanModel = "google:" + cleanModel
	}
	return g.UpdateAgentConfig(agentID, AgentConfigUpdate{
		ModelOverride: &cleanModel,
	})
}

// writeAtomicJSON writes indented JSON data to a temporary file before atomically replacing target.
func writeAtomicJSON(targetPath string, data interface{}) error {
	bytes, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to format JSON: %w", err)
	}
	bytes = append(bytes, '\n')

	tmpPath := targetPath + ".tmp"
	if err := os.WriteFile(tmpPath, bytes, 0644); err != nil {
		return fmt.Errorf("failed to write temporary file %q: %w", tmpPath, err)
	}

	if err := os.Rename(tmpPath, targetPath); err != nil {
		_ = os.Remove(tmpPath)
		return fmt.Errorf("failed to atomically update %q: %w", targetPath, err)
	}

	return nil
}

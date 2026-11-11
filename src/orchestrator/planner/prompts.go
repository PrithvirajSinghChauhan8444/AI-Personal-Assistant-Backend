package planner

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

//go:embed manager_prompt.md
var defaultPromptTemplate string

// DefaultWorkerCapabilities defines the available downstream specialist workers.
var DefaultWorkerCapabilities = []WorkerCapability{
	{
		Name:        "system",
		Description: "Local Linux OS operations: file reading/writing/deletion, shell execution, process monitoring, and git version control.",
		RoutingRules: []string{
			"Assign when inspecting local files, directory trees, terminal scripts, or git repositories.",
		},
	},
	{
		Name:        "browser",
		Description: "Interactive web browser automation: navigating URLs, clicking elements, reading dynamic web pages, and taking screenshots via Playwright.",
		RoutingRules: []string{
			"Assign when a task requires rendering modern JavaScript websites, logging into web dashboards, or visual UI verification.",
		},
	},
	{
		Name:        "research",
		Description: "Deep research, web searching, summarizing articles/papers, fact-checking, and long-term memory retrieval.",
		RoutingRules: []string{
			"Assign when looking up public facts, searching the web, or synthesizing multiple information sources.",
		},
	},
	{
		Name:        "productivity",
		Description: "Personal communication and scheduling: searching and reading Gmail, drafting emails, and creating/updating Google Calendar events.",
		RoutingRules: []string{
			"Assign for all email (Gmail) inquiries, calendar events, meeting scheduling, and personal agendas.",
		},
	},
}

type rawAgentConfig struct {
	Enabled      *bool    `json:"enabled"`
	Description  string   `json:"description"`
	RoutingRules []string `json:"routing_rules"`
}

// DiscoverAndLoadActiveWorkers loads worker capabilities respecting config/agents.json toggles and auto-discovering agents directory.
func DiscoverAndLoadActiveWorkers(configPath, agentsDir string) []WorkerCapability {
	discovered := make(map[string]WorkerCapability)
	for _, w := range DefaultWorkerCapabilities {
		discovered[strings.ToLower(w.Name)] = w
	}

	if agentsDir == "" {
		agentsDir = filepath.Join("src", "agents")
	}
	if entries, err := os.ReadDir(agentsDir); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				name := strings.ToLower(e.Name())
				if name == "manager" || name == "engine" || strings.HasPrefix(name, ".") {
					continue
				}
				if _, exists := discovered[name]; !exists {
					discovered[name] = WorkerCapability{
						Name:        name,
						Description: fmt.Sprintf("Specialist worker in %s operations.", name),
						RoutingRules: []string{
							fmt.Sprintf("Assign for tasks relating to %s.", name),
						},
					}
				}
			}
		}
	}

	if configPath == "" {
		configPath = filepath.Join("config", "agents.json")
	}
	if data, err := os.ReadFile(configPath); err == nil {
		var cfgMap map[string]rawAgentConfig
		if err := json.Unmarshal(data, &cfgMap); err == nil {
			for name, cfg := range cfgMap {
				nameLower := strings.ToLower(name)
				if nameLower == "manager" {
					continue
				}

				if cfg.Enabled != nil && !*cfg.Enabled {
					delete(discovered, nameLower)
					continue
				}

				capItem, exists := discovered[nameLower]
				if !exists {
					capItem = WorkerCapability{Name: nameLower}
				}
				if cfg.Description != "" {
					capItem.Description = cfg.Description
				}
				if len(cfg.RoutingRules) > 0 {
					capItem.RoutingRules = cfg.RoutingRules
				}
				discovered[nameLower] = capItem
			}
		}
	}

	var active []WorkerCapability
	for _, w := range discovered {
		active = append(active, w)
	}
	return active
}

// BuildPlannerSystemPrompt formats the system prompt markdown file with available workers.
func BuildPlannerSystemPrompt(workers []WorkerCapability, promptFilePath string) string {
	template := defaultPromptTemplate

	// If a custom prompt markdown file is specified and exists, load it from disk
	if promptFilePath != "" {
		if content, err := os.ReadFile(promptFilePath); err == nil && len(content) > 0 {
			template = string(content)
		}
	} else {
		// Try default location on disk for live editing
		candidates := []string{
			"src/orchestrator/planner/manager_prompt.md",
			"config/prompts/manager_prompt.md",
		}
		for _, c := range candidates {
			if content, err := os.ReadFile(c); err == nil && len(content) > 0 {
				template = string(content)
				break
			}
		}
	}

	var workerBullets strings.Builder
	for _, w := range workers {
		workerBullets.WriteString(fmt.Sprintf("- %s: %s\n", w.Name, w.Description))
		for _, r := range w.RoutingRules {
			workerBullets.WriteString(fmt.Sprintf("  • %s\n", r))
		}
	}

	return strings.Replace(template, "{{AVAILABLE_WORKERS}}", strings.TrimSpace(workerBullets.String()), 1)
}

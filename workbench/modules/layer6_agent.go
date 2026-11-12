package modules

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"reflect"
	"strings"
	"time"

	"assistant/workbench/engine"
)

// AgentExecutionInput defines parameters to run a Layer 6 Specialised Worker Agent.
type AgentExecutionInput struct {
	AgentType string `json:"agent_type" desc:"Agent persona: system, research, browser, productivity, manager"`
	Prompt    string `json:"prompt" desc:"Input query or instruction for the specialist agent"`
	ModelMode string `json:"model_mode" desc:"'mock' for offline deterministic verification, or 'live' for real LLM"`
	MockTools bool   `json:"mock_tools" desc:"If true, tools are simulated; if false, runs live Go Layer 3 Tool Engine"`
}

func findPythonBinary() string {
	candidates := []string{
		"./.venv/bin/python3",
		"./.venv/bin/python",
		"python3",
		"python",
	}
	for _, c := range candidates {
		if strings.HasPrefix(c, "./") {
			if _, err := os.Stat(c); err == nil {
				return c
			}
		} else {
			if path, err := exec.LookPath(c); err == nil {
				return path
			}
		}
	}
	return "python3"
}

// RegisterLayer6Agent registers the Layer 6 Specialised Agent Engine manual test bench.
func RegisterLayer6Agent(r *engine.Registry) {
	r.Register(engine.Module{
		ID:          "l6_specialised_agent_turn",
		Name:        "Layer 6: Specialised Agent Engine (Execute Agent)",
		Tier:        "LAYER_BENCH",
		Layer:       "layer6",
		Category:    "Layer 6: Specialised Agents",
		Description: "Invokes an isolated specialist worker agent (@system, @research, @browser, @productivity, @manager) through the cognitive ReAct loop with thought streaming and live Go tool execution.",
		InputType:   reflect.TypeOf(AgentExecutionInput{}),
		Presets: []engine.Preset{
			{
				ID:          "system_agent_git",
				Name:        "@system: Inspect Git Working Tree",
				Category:    "System Agent",
				Description: "Prompts System Agent to inspect git status and active branch",
				Payload: AgentExecutionInput{
					AgentType: "system",
					Prompt:    "Check git status and summarize the current branch state",
					ModelMode: "mock",
					MockTools: false,
				},
			},
			{
				ID:          "system_agent_file",
				Name:        "@system: Read and Audit Project Config",
				Category:    "System Agent",
				Description: "Prompts System Agent to read go.mod via Layer 3 Tool Engine",
				Payload: AgentExecutionInput{
					AgentType: "system",
					Prompt:    "Read go.mod and report the Go version and core dependencies",
					ModelMode: "mock",
					MockTools: false,
				},
			},
			{
				ID:          "research_agent_docs",
				Name:        "@research: Deep Architecture Inquiry",
				Category:    "Research Agent",
				Description: "Prompts Research Agent to synthesize subsystem isolation contracts",
				Payload: AgentExecutionInput{
					AgentType: "research",
					Prompt:    "Explain the role of Layer 3 Tool Engine and its isolation contracts",
					ModelMode: "mock",
					MockTools: true,
				},
			},
			{
				ID:          "browser_agent_nav",
				Name:        "@browser: Web Spec Extraction",
				Category:    "Browser Agent",
				Description: "Prompts Browser Agent to search documentation and navigate endpoints",
				Payload: AgentExecutionInput{
					AgentType: "browser",
					Prompt:    "Fetch API endpoints from https://example.com and check status",
					ModelMode: "mock",
					MockTools: true,
				},
			},
			{
				ID:          "productivity_agent_email",
				Name:        "@productivity: Email Inbox Triage",
				Category:    "Productivity Agent",
				Description: "Prompts Productivity Agent to query Gmail and schedule calendar",
				Payload: AgentExecutionInput{
					AgentType: "productivity",
					Prompt:    "List unread messages from the last 24 hours",
					ModelMode: "mock",
					MockTools: true,
				},
			},
			{
				ID:          "manager_agent_plan",
				Name:        "@manager: Plan Subsystem Work Unit",
				Category:    "Manager Agent",
				Description: "Prompts Manager Agent to decompose a multi-layer development task",
				Payload: AgentExecutionInput{
					AgentType: "manager",
					Prompt:    "Decompose the implementation of Layer 4 IPC Bridge into verifiable tasks",
					ModelMode: "mock",
					MockTools: true,
				},
			},
		},
		Execute: func(ctx context.Context, inputRaw json.RawMessage, stream chan<- engine.StreamEvent) (any, error) {
			var in AgentExecutionInput
			if err := json.Unmarshal(inputRaw, &in); err != nil {
				return nil, fmt.Errorf("invalid json for AgentExecutionInput: %w", err)
			}

			if in.AgentType == "" {
				in.AgentType = "system"
			}
			if in.Prompt == "" {
				in.Prompt = "Check system status"
			}
			if in.ModelMode == "" {
				in.ModelMode = "mock"
			}

			pyBin := findPythonBinary()

			args := []string{
				"-m", "src.agents.bench",
				"--agent", in.AgentType,
				"--prompt", in.Prompt,
			}
			if in.ModelMode == "mock" {
				args = append(args, "--mock-llm")
			}
			if in.MockTools {
				args = append(args, "--mock-tools")
			}

			cmd := exec.CommandContext(ctx, pyBin, args...)
			cmd.Dir = "."
			cmd.Env = append(os.Environ(), "PYTHONUNBUFFERED=1")

			stdoutPipe, err := cmd.StdoutPipe()
			if err != nil {
				return nil, fmt.Errorf("failed to open stdout pipe: %w", err)
			}
			stderrPipe, err := cmd.StderrPipe()
			if err != nil {
				return nil, fmt.Errorf("failed to open stderr pipe: %w", err)
			}

			stream <- engine.StreamEvent{
				Index:     1,
				Timestamp: time.Now(),
				Type:      "AGENT_INIT",
				AgentName: fmt.Sprintf("@%s", in.AgentType),
				Payload: map[string]any{
					"agent":      in.AgentType,
					"model_mode": in.ModelMode,
					"mock_tools": in.MockTools,
					"prompt":     in.Prompt,
				},
			}

			if err := cmd.Start(); err != nil {
				return nil, fmt.Errorf("failed to start agent subprocess: %w", err)
			}

			eventIdx := 1
			var responseBuf strings.Builder
			var stderrBuf strings.Builder

			go func() {
				slurp, _ := io.ReadAll(stderrPipe)
				stderrBuf.Write(slurp)
			}()

			scanner := bufio.NewScanner(stdoutPipe)
			inFinalResponse := false

			for scanner.Scan() {
				line := scanner.Text()
				trimmed := strings.TrimSpace(line)

				if strings.Contains(line, "[") && strings.Contains(line, "Thought]:") {
					parts := strings.SplitN(line, "Thought]:", 2)
					thought := strings.TrimSpace(parts[1])
					eventIdx++
					stream <- engine.StreamEvent{
						Index:     eventIdx,
						Timestamp: time.Now(),
						Type:      "AGENT_THOUGHT",
						AgentName: fmt.Sprintf("@%s", in.AgentType),
						Payload:   thought,
					}
				} else if strings.HasPrefix(trimmed, ">>> [") {
					// Tool Intent
					toolPart := strings.TrimPrefix(trimmed, ">>> [")
					toolParts := strings.SplitN(toolPart, "]:", 2)
					toolName := toolParts[0]
					toolArgs := "{}"
					if len(toolParts) > 1 {
						toolArgs = strings.TrimSpace(toolParts[1])
					}
					eventIdx++
					stream <- engine.StreamEvent{
						Index:     eventIdx,
						Timestamp: time.Now(),
						Type:      "TOOL_INTENT",
						AgentName: toolName,
						Payload:   toolArgs,
					}
				} else if strings.Contains(line, "Final Response:") {
					inFinalResponse = true
					continue
				} else if inFinalResponse {
					if strings.HasPrefix(trimmed, "============================================================") {
						continue
					}
					responseBuf.WriteString(line + "\n")
				} else if trimmed != "" && !strings.HasPrefix(trimmed, "=") && !strings.HasPrefix(trimmed, "Testing Agent:") && !strings.HasPrefix(trimmed, "Prompt:") && !strings.HasPrefix(trimmed, "Notice:") {
					eventIdx++
					stream <- engine.StreamEvent{
						Index:     eventIdx,
						Timestamp: time.Now(),
						Type:      "AGENT_TOKEN",
						AgentName: fmt.Sprintf("@%s", in.AgentType),
						Payload:   line,
					}
				}
			}

			waitErr := cmd.Wait()
			finalResp := strings.TrimSpace(responseBuf.String())
			if finalResp == "" {
				if trimmedStderr := strings.TrimSpace(stderrBuf.String()); trimmedStderr != "" {
					finalResp = trimmedStderr
				}
			}

			eventIdx++
			stream <- engine.StreamEvent{
				Index:     eventIdx,
				Timestamp: time.Now(),
				Type:      "AGENT_RESPONSE",
				AgentName: fmt.Sprintf("@%s", in.AgentType),
				Payload:   finalResp,
			}

			if waitErr != nil {
				return map[string]any{
					"status":     "ERROR",
					"agent":      in.AgentType,
					"error":      waitErr.Error(),
					"stderr":     stderrBuf.String(),
					"raw_output": finalResp,
				}, waitErr
			}

			return map[string]any{
				"status":         "SUCCESS",
				"agent":          in.AgentType,
				"prompt":         in.Prompt,
				"model_mode":     in.ModelMode,
				"final_response": finalResp,
			}, nil
		},
	})
}

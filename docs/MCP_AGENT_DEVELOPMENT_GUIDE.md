# MCP & Agent Development Guide: Architecture, Structure & Integration

This guide provides the complete architectural standard for creating, structuring, and integrating **MCP-powered tools** and **Specialist Agents** into the AI Personal Assistant Backend.

---

## 1. Architectural Philosophy: Capabilities vs. Actors

To maintain a clean, scalable codebase that does not devolve into ad-hoc folders:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Layer 1 & 2: Gateway & DAG Planner             │
│   (Receives user prompt, decomposes intent, delegates subtasks)        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Assigns task
┌───────────────────────────────────▼────────────────────────────────────┐
│                  Layer 6: Specialist Worker Agents (Python)            │
│   (Cognitive actors with prompts, ReAct reasoning loops, & memory)     │
│   Examples: ResearchAgent, BrowserAgent, ProductivityAgent             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Emits tool call
┌───────────────────────────────────▼────────────────────────────────────┐
│                    Layer 3: Tool Engine & MCP Hub (Go)                 │
│   - Go Tool Dispatcher routes calls                                    │
│   - Go MCP Hub manages external server processes over JSON-RPC         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Executes via stdio / SSE
┌───────────────────────────────────▼────────────────────────────────────┐
│                      External MCP Servers & Native Tools               │
│   - Python/Node MCP Servers (mcp_servers/youtube_server.py, Playwright)│
│   - Native OS Tools (sys, fs, git, hyprland)                           │
└────────────────────────────────────────────────────────────────────────┘
```

### The Golden Rule:
* **Tools / MCP Servers are Hands**: They are passive, deterministic execution endpoints (e.g., query SQLite, extract YouTube transcript, click web element). They do **not** run an LLM.
* **Agents are Brains**: They are active personas with an LLM prompt, context window, and reasoning loop.
* **Do NOT make an MCP server into an agent** unless the domain itself requires multi-turn autonomous reasoning, self-reflection, and contextual decision-making.

---

## 2. Directory Structure Blueprint

All components must strictly adhere to this standardized layout:

```bash
AI-Personal-Assistant-Backend/
│
├── config/                             # Declarative Configurations
│   ├── agents.json                     # Active agents, model overrides, routing rules
│   ├── mcp_servers.json                # MCP server definitions (stdio/SSE commands)
│   └── tools.json                      # Native tool toggle policies
│
├── mcp_servers/                        # Standalone MCP Servers (Python/Node)
│   ├── base.py                         # Reusable JSON-RPC 2.0 stdio server base
│   ├── youtube_server.py               # YouTube transcript & search MCP server
│   └── excalidraw_server.py            # Diagram generation MCP server
│
├── src/
│   ├── mcp/                            # Go MCP Protocol & Client Subsystem
│   │   ├── config.go                   # Parses config/mcp_servers.json
│   │   ├── protocol.go                 # JSON-RPC 2.0 types & schemas
│   │   ├── server.go                   # Process supervisor (stdio pipes)
│   │   ├── tool.go                     # MCPTool adapter (adapts MCP to Tool interface)
│   │   └── hub.go                      # Starts all servers & aggregates tools
│   │
│   ├── tools/                          # Go Tool Registry & Native Capabilities
│   │   ├── contracts.go                # Tool & ToolMetadata interfaces
│   │   ├── registry.go                 # In-memory ToolRegistry
│   │   ├── dispatcher.go               # Tool registration & execution dispatcher
│   │   ├── fs/                         # File system tools
│   │   ├── git/                        # Git inspection tools
│   │   ├── hyprland/                   # Desktop/window automation tools
│   │   ├── net/                        # Network & weather tools
│   │   ├── sys/                        # Process execution & system status tools
│   │   └── workspace/                  # Google Workspace (Gmail, Calendar, Tasks)
│   │
│   └── agents/                         # Layer 6 Cognitive Specialist Agents (Python)
│       ├── contracts.py                # AgentContext, AgentType, ToolDefinition
│       ├── factory.py                  # Dynamic agent loader & constructor
│       ├── manifest.py                 # Agent manifest validator
│       ├── engine/                     # ReAct execution loop & prompt formatting
│       │
│       │   # Standard 4-File Agent Package (Every agent has this structure):
│       └── <agent_name>/
│           ├── <agent_name>_config.json # Identity, declared capabilities, routing rules
│           ├── prompt.md                # System instructions & operational directives
│           ├── prompts.py               # Prompt loader helper
│           ├── agent.py                 # Agent class implementing execute_turn()
│           └── tools.py                 # ToolDefinition schemas exposed to the LLM
```

---

## 3. Workflow A: Giving New MCP Tools to an Existing Agent (2 Minutes)

Use this when you want an existing specialist (e.g., `ResearchAgent` or `ProductivityAgent`) to gain new capabilities.

### Step 1: Add the MCP Server to `config/mcp_servers.json`
```json
{
  "mcpServers": {
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"],
      "enabled": true
    }
  }
}
```

### Step 2: Declare the Tools in the Agent Manifest
Open `src/agents/research/research_config.json` and add the namespaced tool:
```json
{
  "name": "fetch__fetch",
  "description": "Fetches a web page URL and converts it into clean Markdown.",
  "risk": "LOW",
  "execution_domain": "mcp_bridge",
  "required_capability": "mcp:fetch"
}
```

### Step 3: Add the Tool Schema to the Agent's `tools.py`
Open `src/agents/research/tools.py` and append:
```python
ToolDefinition(
    name="fetch__fetch",
    category="mcp",
    description="Fetches a web page URL and converts it into clean Markdown.",
    risk="LOW",
    prompt_usage_tip="Use to read documentation or web articles quickly without browser overhead.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full HTTP/HTTPS URL"}
        },
        "required": ["url"],
    },
)
```

### Step 4: Mention the Tool in `prompt.md`
Add a brief bullet point to `src/agents/research/prompt.md` under Core Capabilities so the LLM understands when to pick it.

---

## 4. Workflow B: Creating a Brand New MCP-Powered Agent

Use this when you need an autonomous agent dedicated to a specialized problem domain (e.g., `GithubAgent` for code review and PR triage, or `DatabaseAgent` for schema migration and SQL tuning).

Let's walk through creating a **`github`** agent as an end-to-end example:

### Step 1: Configure the MCP Server
In `config/mcp_servers.json`:
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      },
      "enabled": true
    }
  }
}
```

### Step 2: Register the Agent in `config/agents.json`
Add the new agent to `config/agents.json`:
```json
{
  "github": {
    "config_path": "src/agents/github/github_config.json",
    "enabled": true,
    "model_override": null,
    "temperature": 0.1
  }
}
```

### Step 3: Create the 4-File Agent Package in `src/agents/github/`

#### File 1: `src/agents/github/github_config.json` (Manifest)
```json
{
  "$schema": "https://assistant.local/schemas/agent_manifest_v1.json",
  "agent_identifier": "github",
  "display_name": "GitHub Specialist Agent",
  "version": "1.0.0",
  "agent_aliases": ["github", "gh", "git_review"],
  "fallback_capability": "system",
  "model": {
    "default": "google:gemini-3.5-flash-lite",
    "temperature": 0.1
  },
  "description": "GitHub repository manager: reviews PRs, inspects issues, searches code, and tracks repository events.",
  "routing_rules": [
    "Assign when a user asks about GitHub issues, pull requests, commits, or repository triage."
  ],
  "tools": [
    {
      "name": "github__search_repositories",
      "description": "Searches GitHub repositories by query.",
      "risk": "LOW",
      "execution_domain": "mcp_bridge",
      "required_capability": "mcp:github"
    },
    {
      "name": "github__get_issue",
      "description": "Fetches details and comments for an issue.",
      "risk": "LOW",
      "execution_domain": "mcp_bridge",
      "required_capability": "mcp:github"
    }
  ]
}
```

#### File 2: `src/agents/github/prompt.md` (System Instructions)
```markdown
# GitHub Agent Prompt

You are GitHubAgent, the repository intelligence and issue triage specialist of the AI Personal Assistant.

## Core Capabilities
- `github__search_repositories`: Queries GitHub for repositories.
- `github__get_issue`: Retrieves full issue details and comment threads.

## Operational Directives
- Always link issue and PR references using standard markdown: `[#123](url)`.
- Summarize long discussion threads objectively before proposing actions.
```

#### File 3: `src/agents/github/prompts.py` (Prompt Loader)
```python
"""Prompt loader for GitHubAgent."""
from pathlib import Path

_PROMPT_PATH = Path(__file__).parent / "prompt.md"

def get_github_prompt() -> str:
    if _PROMPT_PATH.is_file():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    return "You are GitHubAgent, repository specialist."
```

#### File 4: `src/agents/github/tools.py` (Tool Definitions)
```python
"""Tool definitions for GitHubAgent."""
from typing import List
from src.agents.contracts import ToolDefinition

GITHUB_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="github__search_repositories",
        category="mcp",
        description="Searches GitHub repositories by query.",
        risk="LOW",
        prompt_usage_tip="Use when user wants to find repositories or libraries on GitHub.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="github__get_issue",
        category="mcp",
        description="Fetches details and comments for an issue.",
        risk="LOW",
        prompt_usage_tip="Use when reading an issue or bug report.",
        parameters={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "issue_number": {"type": "integer", "description": "Issue number"}
            },
            "required": ["owner", "repo", "issue_number"],
        },
    ),
]
```

#### File 5: `src/agents/github/agent.py` (Turn Runner)
```python
"""GitHubAgent implementation."""
from typing import Any, Dict, List, Optional
from src.agents.github.prompts import get_github_prompt
from src.agents.github.tools import GITHUB_TOOLS
from src.agents.contracts import AgentContext, AgentTurnResult
from src.agents.engine.react_engine import run_worker_agent
from src.models.base import BaseLLMClient

class GithubAgent:
    """Specialist worker for GitHub API management and repository triage."""

    def __init__(self, model_client: BaseLLMClient) -> None:
        self.model_client = model_client
        self.agent_type = "github"
        self.system_prompt = get_github_prompt()
        self.tools = GITHUB_TOOLS

    async def execute_turn(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        pipe_emitter: Optional[Any] = None,
        pipe_reader: Optional[Any] = None,
        memory_engine: Optional[Any] = None,
        max_iterations: int = 10,
    ) -> AgentTurnResult:
        ctx = AgentContext(
            session_id=session_id,
            turn_id=turn_id,
            agent_type=self.agent_type,
            user_prompt=prompt,
            system_prompt=self.system_prompt,
            conversation_history=history or [],
            available_tools=self.tools,
            max_iterations=max_iterations,
        )
        return await run_worker_agent(
            ctx=ctx,
            model_client=self.model_client,
            memory_engine=memory_engine,
            pipe_emitter=pipe_emitter,
            pipe_reader=pipe_reader,
        )
```

### Step 4: Register the Agent Enum in `src/agents/contracts.py`
Add to `AgentType`:
```python
class AgentType(str, Enum):
    MANAGER = "manager"
    SYSTEM = "system"
    RESEARCH = "research"
    BROWSER = "browser"
    PRODUCTIVITY = "productivity"
    MEMORY = "memory"
    SUMMARIZER = "summarizer"
    GITHUB = "github"  # <-- Added
```

### Step 5: Inform the Orchestrator Planner
In `src/orchestrator/planner/manager_prompt.md`, add your new agent under **Worker Personas**:
```markdown
- `github`: Dedicated GitHub issue reader, PR reviewer, and repository code searcher.
```
Your DAG planner now understands when to dispatch tasks to your new `github` agent.

---

## 5. How to Write a Custom Python MCP Server

When an off-the-shelf MCP server does not exist (like your custom YouTube transcript or Excalidraw servers), create one in `mcp_servers/` using `mcp_servers/base.py`:

```python
"""mcp_servers/my_custom_server.py"""
from base import SimpleMCPServer
from typing import Dict, Any

def handle_my_tool(args: Dict[str, Any]) -> str:
    name = args.get("name", "World")
    return f"Hello, {name}!"

def main():
    server = SimpleMCPServer("my_custom_server", "1.0.0")
    
    server.register_tool(
        name="say_hello",
        description="Greets the user by name.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Person to greet"}
            },
            "required": ["name"]
        },
        handler=handle_my_tool,
    )
    
    server.run()

if __name__ == "__main__":
    main()
```

### Critical Rules for Custom Servers:
1. **Never print unformatted text to `sys.stdout`**:
   The MCP host communicates over `sys.stdout` via JSON-RPC. If you use `print("debug")`, you will corrupt the JSON stream. Always use `print("debug", file=sys.stderr)` for logging.
2. **Always Catch Exceptions**:
   Wrap your handler routines in `try ... except` and return clean error messages in string format so the calling agent can self-heal.
3. **Namespacing**:
   The Go MCP Hub automatically prefixes tool names with `<server_name>__` (e.g. `my_custom_server__say_hello`).

---

## 6. Verification & Testing Checklist

Before shipping any new MCP server or agent, run these verification steps:

```bash
# 1. Test Go MCP Hub discovery & tool execution
go test -v -count=1 ./src/mcp/...

# 2. Test entire Go build
go build ./...

# 3. Test Python agent manifests loading
PYTHONPATH=. .venv/bin/python -c "
from src.agents.manifest import load_active_manifests
manifests = load_active_manifests('config/agents.json')
print(f'Active agents: {list(manifests.keys())}')
"
```

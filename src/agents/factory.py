"""Factory functions to instantiate and wire Layer 6 Specialist Worker Agents."""

import json
import os
from typing import Any, Dict, Optional

from src.agents.browser.agent import BrowserAgent
from src.agents.contracts import AgentType
from src.agents.productivity.agent import ProductivityAgent
from src.agents.research.agent import ResearchAgent
from src.agents.system.agent import SystemAgent
from src.models.base import BaseLLMClient
from src.models.factory import ModelFactory


def load_agents_config(config_path: str = "config/agents.json") -> Dict[str, Any]:
    """Loads configuration for agents from JSON."""
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_system_config(config_path: str = "config/system.json") -> Dict[str, Any]:
    """Loads system configuration (workspace paths, limits, etc.) from JSON."""
    candidates = [
        config_path,
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "system.json"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {
        "workspace_dir": "workspace",
        "artifacts_dir": "workspace/artifacts",
        "database_path": "workspace/data/sessions.db",
        "notes_dir": "workspace/obsidian_vault",
        "allowed_access_roots": ["workspace"],
    }


def create_agent(
    agent_type: AgentType,
    model_client: Optional[BaseLLMClient] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Any:
    """Instantiates an isolated specialist worker agent with configured or provided LLM client."""
    if not model_client:
        agent_cfg = (config or {}).get(agent_type.value, {})
        model_name = agent_cfg.get("model", "google:gemini-3.5-flash-lite")
        temperature = agent_cfg.get("temperature", 0.0)
        model_client = ModelFactory.get_client(model_id=model_name, temperature=temperature)

    if agent_type == AgentType.SYSTEM:
        return SystemAgent(model_client=model_client)
    elif agent_type == AgentType.RESEARCH:
        return ResearchAgent(model_client=model_client)
    elif agent_type == AgentType.BROWSER:
        return BrowserAgent(model_client=model_client)
    elif agent_type == AgentType.PRODUCTIVITY:
        return ProductivityAgent(model_client=model_client)
    else:
        raise ValueError(f"Unknown worker agent type: {agent_type}")


def create_all_agents(
    model_client: Optional[BaseLLMClient] = None,
    config_path: str = "config/agents.json",
) -> Dict[AgentType, Any]:
    """Instantiates all Layer 6 specialist worker agents."""
    config = load_agents_config(config_path)

    system_worker = create_agent(AgentType.SYSTEM, model_client, config)
    research_worker = create_agent(AgentType.RESEARCH, model_client, config)
    browser_worker = create_agent(AgentType.BROWSER, model_client, config)
    productivity_worker = create_agent(AgentType.PRODUCTIVITY, model_client, config)

    return {
        AgentType.SYSTEM: system_worker,
        AgentType.RESEARCH: research_worker,
        AgentType.BROWSER: browser_worker,
        AgentType.PRODUCTIVITY: productivity_worker,
    }

"""Factory functions to instantiate and wire Layer 6 Specialist Worker Agents."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.agents.browser.agent import BrowserAgent
from src.agents.contracts import AgentType
from src.agents.manifest import find_agent_config, load_manifest, sync_control_registry
from src.agents.memory.agent import MemoryAgent
from src.agents.productivity.agent import ProductivityAgent
from src.agents.research.agent import ResearchAgent
from src.agents.summarizer.agent import SummarizerAgent
from src.agents.system.agent import SystemAgent
from src.agents.engine.tool_dispatcher import ToolDispatcher
from src.models.base import BaseLLMClient
from src.models.factory import ModelFactory

_STATIC_AGENT_CLASSES: Dict[str, type] = {
    "system": SystemAgent,
    "browser": BrowserAgent,
    "research": ResearchAgent,
    "productivity": ProductivityAgent,
    "memory": MemoryAgent,
    "summarizer": SummarizerAgent,
}


def load_agents_config(config_path: str = "config/agents.json") -> Dict[str, Any]:
    """Loads configuration for agents from JSON."""
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return {}


def load_system_config(config_path: str = "config/system.json") -> Dict[str, Any]:
    """Loads system configuration (workspace paths, limits, etc.) from JSON."""
    if not os.path.exists(config_path):
        return {
            "workspace_dir": "workspace",
            "artifacts_dir": "workspace/artifacts",
            "database_path": "workspace/data/sessions.db",
            "notes_dir": "workspace/obsidian_vault",
            "allowed_access_roots": ["workspace"],
        }
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _resolve_agent_name(agent_type: Union[AgentType, str]) -> str:
    """Normalizes an AgentType enum or string to a lowercase canonical name."""
    if hasattr(agent_type, "value"):
        return str(agent_type.value).lower().strip()
    return str(agent_type).lower().strip()


def _resolve_model_client(
    agent_name: str,
    config: Optional[Dict[str, Any]] = None,
    manifest_path: Optional[str] = None,
) -> BaseLLMClient:
    """Resolves and constructs the LLM client from manifest or config overrides."""
    manifest_file: Optional[Path] = None
    if manifest_path:
        cand = Path(manifest_path)
        if cand.is_file():
            manifest_file = cand

    if not manifest_file:
        manifest_file = find_agent_config(f"src/agents/{agent_name}", agent_name)

    manifest = load_manifest(manifest_file) if manifest_file else None

    default_model = manifest.model.default if manifest else "google:gemini-3.5-flash-lite"
    default_temp = manifest.model.temperature if manifest else 0.0

    agent_cfg = (config or {}).get(agent_name, {})
    raw_override = agent_cfg.get("model_override")
    override_dict = raw_override if isinstance(raw_override, dict) else {}
    override_model = raw_override if isinstance(raw_override, str) else override_dict.get("model")

    model_name = override_model or agent_cfg.get("model") or default_model
    temp_val = override_dict.get("temperature") or agent_cfg.get("temperature")
    temperature = float(temp_val) if temp_val is not None else default_temp

    return ModelFactory.get_client(model_id=model_name, temperature=temperature)


def _load_agent_class(agent_name: str) -> Optional[type]:
    """Dynamically loads the agent class from src.agents.<name>.agent."""
    module_name = f"src.agents.{agent_name}.agent"
    try:
        module = importlib.import_module(module_name)

        expected_class_name = "".join(part.capitalize() for part in agent_name.split("_")) + "Agent"
        if hasattr(module, expected_class_name):
            return getattr(module, expected_class_name)

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if hasattr(obj, "execute_turn") and obj.__module__ == module_name:
                return obj
    except ModuleNotFoundError as err:
        # Re-raise if the error is caused by a missing dependency INSIDE agent.py
        if err.name != module_name and not module_name.startswith(f"{err.name}."):
            raise
    except AttributeError:
        pass

    return _STATIC_AGENT_CLASSES.get(agent_name)


def create_agent(
    agent_type: Union[AgentType, str],
    model_client: Optional[BaseLLMClient] = None,
    config: Optional[Dict[str, Any]] = None,
    tool_dispatcher: Optional[ToolDispatcher] = None,
) -> Any:
    """Instantiates a specialist worker agent dynamically with configured LLM client and optional tool dispatcher."""
    agent_name = _resolve_agent_name(agent_type)
    if config is not None:
        agent_cfg = config.get(agent_name, {})
        if isinstance(agent_cfg, dict) and not agent_cfg.get("enabled", True):
            raise ValueError(f"Cannot instantiate worker '{agent_name}': agent is disabled in config/agents.json.")

    if not model_client:
        agent_cfg = (config or {}).get(agent_name, {})
        manifest_path = agent_cfg.get("config_path") or agent_cfg.get("manifest_path")
        model_client = _resolve_model_client(agent_name, config, manifest_path)

    agent_cls = _load_agent_class(agent_name)
    if not agent_cls:
        raise ValueError(f"Unknown or unresolvable worker agent type: {agent_type}")

    sig = inspect.signature(agent_cls)
    kwargs: Dict[str, Any] = {"model_client": model_client}
    if tool_dispatcher is not None and "tool_dispatcher" in sig.parameters:
        kwargs["tool_dispatcher"] = tool_dispatcher

    return agent_cls(**kwargs)


def create_all_agents(
    model_client: Optional[BaseLLMClient] = None,
    config_path: str = "config/agents.json",
    tool_dispatcher: Optional[ToolDispatcher] = None,
) -> Dict[Any, Any]:
    """Instantiates all active Layer 6 specialist worker agents with optional shared tool dispatcher."""
    agents_dir = Path("src/agents")
    sync_control_registry(config_path, agents_dir)
    config = load_agents_config(config_path)

    discovered_agents: Dict[str, Any] = {}

    # Discovered from config entries
    for name, entry in config.items():
        name_lower = name.lower()
        if name_lower == "manager":
            continue
        if isinstance(entry, dict) and not entry.get("enabled", True):
            continue
        discovered_agents[name_lower] = entry

    # Also discover directories in src/agents/ that have an agent config
    if agents_dir.is_dir():
        for child in agents_dir.iterdir():
            if child.is_dir() and not child.name.startswith((".", "_")) and child.name not in ("manager", "engine"):
                if find_agent_config(child, child.name):
                    name_lower = child.name.lower()
                    if name_lower not in discovered_agents:
                        user_cfg = config.get(name_lower, {})
                        if user_cfg.get("enabled", True):
                            discovered_agents[name_lower] = user_cfg

    instantiated: Dict[Any, Any] = {}
    for name in discovered_agents:
        try:
            if tool_dispatcher is not None:
                worker = create_agent(name, model_client, config, tool_dispatcher=tool_dispatcher)
            else:
                worker = create_agent(name, model_client, config)
            try:
                enum_key = AgentType(name)
                instantiated[enum_key] = worker
            except ValueError:
                pass
            instantiated[name] = worker
        except Exception as exc:
            sys.stderr.write(f"[factory] Warning: failed to initialize worker '{name}': {exc}\n")

    return instantiated

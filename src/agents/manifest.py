"""Agent Manifest specifications and dynamic loader for Layer 6 Agents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ToolContract:
    """Declared tool contract within an agent manifest."""
    name: str
    description: str = ""
    risk: str = "LOW"
    execution_domain: str = "go_native"
    required_capability: str = ""


@dataclass
class ModelConfig:
    """Agent LLM model configuration."""
    default: str = "google:gemini-3.5-flash-lite"
    temperature: float = 0.0


@dataclass
class AgentManifest:
    """Self-contained, portable agent identity and cognitive specification."""
    agent_identifier: str
    display_name: str
    version: str = "1.0.0"
    agent_aliases: List[str] = field(default_factory=list)
    fallback_capability: str = "system"
    model: ModelConfig = field(default_factory=ModelConfig)
    description: str = ""
    routing_rules: List[str] = field(default_factory=list)
    tools: List[ToolContract] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentManifest:
        model_raw = data.get("model", {})
        model_cfg = ModelConfig(
            default=model_raw.get("default", "google:gemini-3.5-flash-lite"),
            temperature=float(model_raw.get("temperature", 0.0)),
        )

        tools_raw = data.get("tools", [])
        tool_contracts: List[ToolContract] = []
        for t in tools_raw:
            if isinstance(t, dict):
                tool_contracts.append(
                    ToolContract(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                        risk=t.get("risk", "LOW").upper(),
                        execution_domain=t.get("execution_domain", "go_native"),
                        required_capability=t.get("required_capability", ""),
                    )
                )

        return cls(
            agent_identifier=data.get("agent_identifier", "").lower(),
            display_name=data.get("display_name", ""),
            version=data.get("version", "1.0.0"),
            agent_aliases=[str(a).lower() for a in data.get("agent_aliases", [])],
            fallback_capability=data.get("fallback_capability", "system"),
            model=model_cfg,
            description=data.get("description", ""),
            routing_rules=data.get("routing_rules", []),
            tools=tool_contracts,
        )


def find_agent_config(agent_dir: str | Path, name: str) -> Optional[Path]:
    """Resolves standard config file (<name>_config.json, manifest.json, agent.json) in agent_dir."""
    dir_path = Path(agent_dir)
    candidates = [
        dir_path / f"{name.lower()}_config.json",
        dir_path / "manifest.json",
        dir_path / "agent.json",
    ]
    return next((c for c in candidates if c.is_file()), None)


def load_manifest(manifest_path: str | Path) -> Optional[AgentManifest]:
    """Loads and validates a single agent config JSON file."""
    path = Path(manifest_path)
    if not path.is_file():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AgentManifest.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return None


def sync_control_registry(
    config_path: str | Path = "config/agents.json",
    agents_dir: str | Path = "src/agents",
) -> bool:
    """Scans agents_dir and registers newly discovered agents into config/agents.json with enabled=False."""
    cfg_file = Path(config_path)
    agents_base = Path(agents_dir)
    if not agents_base.is_dir():
        return False

    registry: Dict[str, Any] = {}
    if cfg_file.is_file():
        try:
            content = cfg_file.read_text(encoding="utf-8").strip()
            if content:
                registry = json.loads(content)
        except Exception:
            return False  # Abort immediately; do not wipe config on parse error

    changed = False

    # Ensure Manager agent entry is always present and enabled
    if "manager" not in registry:
        registry["manager"] = {
            "enabled": True,
            "model": "google:gemini-3.5-flash-lite",
            "temperature": 0.1,
            "max_parallel_workers": 4,
            "auto_heal_deadlocks": True,
            "description": "Layer 2 Cognitive Planner that decomposes user requests into actionable DAG task plans.",
        }
        changed = True

    for child in agents_base.iterdir():
        if not child.is_dir():
            continue
        name = child.name.lower()
        if name in ("manager", "engine") or name.startswith((".", "_")):
            continue

        found_config = find_agent_config(child, name)
        if not found_config:
            continue

        if name not in registry:
            registry[name] = {
                "enabled": False,
                "config_path": found_config.as_posix(),
                "model_override": None,
            }
            changed = True

    if changed:
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2)
                f.write("\n")
        except OSError:
            return False

    return changed


def load_active_manifests(
    config_path: str | Path = "config/agents.json",
    agents_dir: str | Path = "src/agents",
) -> Dict[str, AgentManifest]:
    """Loads all manifests for active/enabled agents according to control registry."""
    cfg_file = Path(config_path)
    if not cfg_file.is_file():
        return {}

    try:
        content = cfg_file.read_text(encoding="utf-8").strip()
        registry = json.loads(content) if content else {}
    except (json.JSONDecodeError, OSError):
        return {}

    agents_base = Path(agents_dir)
    manifests: Dict[str, AgentManifest] = {}

    for name, entry in registry.items():
        if name.lower() == "manager":
            continue
        if isinstance(entry, dict) and not entry.get("enabled", True):
            continue

        manifest_file: Optional[Path] = None
        if isinstance(entry, dict):
            explicit_path = entry.get("config_path") or entry.get("manifest_path")
            if explicit_path:
                candidate = Path(explicit_path)
                if candidate.is_file():
                    manifest_file = candidate

        if manifest_file is None or not manifest_file.is_file():
            manifest_file = find_agent_config(agents_base / name, name)

        if manifest_file:
            manifest = load_manifest(manifest_file)
            if manifest:
                ident = manifest.agent_identifier or name.lower()
                manifests[ident] = manifest

    return manifests

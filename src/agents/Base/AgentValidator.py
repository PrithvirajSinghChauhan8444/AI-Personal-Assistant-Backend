"""Configuration validation, identity inference, and diagnostics for BaseAgent."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from src.agents.contracts import AgentType, ToolDefinition
from src.models.base import BaseLLMClient


class AgentValidator:
    """Validates configuration, infers identities, and formats agent diagnostics."""

    @staticmethod
    def infer_name(class_name: str) -> str:
        """Converts a CamelCase class name to a snake_case identifier."""
        name = class_name
        if name.endswith("Agent") and len(name) > 5:
            name = name[:-5]
        step1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step1).lower()

    @staticmethod
    def validate_runtime(model_client: BaseLLMClient, max_iterations: int) -> None:
        """Validates execution runtime invariants."""
        if not model_client:
            raise ValueError("Model client is missing or unconfigured")
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")

    @classmethod
    def validate_agent(cls, agent: Any) -> None:
        """Coordinates validation checks across all agent subsystems."""
        cls.validate_runtime(agent._model_client, agent._max_iterations)
        try:
            agent.prompts.validate()
        except ValueError as err:
            raise ValueError(f"Agent '{agent.agent_name}' has an empty system prompt") from err
        try:
            agent.registry.validate()
        except ValueError as err:
            raise ValueError(f"Encountered tool with empty name in agent '{agent.agent_name}'") from err

    @classmethod
    def validate_configuration(
        cls,
        agent_name: str,
        model_client: BaseLLMClient,
        system_prompt: str,
        max_iterations: int,
        tools: List[ToolDefinition],
    ) -> None:
        """Validates configuration invariants across runtime, prompt, and tool parameters."""
        cls.validate_runtime(model_client, max_iterations)
        if not system_prompt or not system_prompt.strip():
            raise ValueError(f"Agent '{agent_name}' has an empty system prompt")
        for tool in tools:
            if not tool.name or not tool.name.strip():
                raise ValueError(f"Encountered tool with empty name in agent '{agent_name}'")

    @staticmethod
    def describe(
        agent_name: str,
        agent_type: Union[AgentType, str],
        model_client: BaseLLMClient,
        tools: List[ToolDefinition],
        max_iterations: int,
        manifest: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Produces structured telemetry metadata for an agent."""
        type_str = str(agent_type.value if hasattr(agent_type, "value") else agent_type)
        model_repr = getattr(model_client, "model_name", str(model_client))
        info: Dict[str, Any] = {
            "agent_name": agent_name,
            "agent_type": type_str,
            "model": model_repr,
            "tool_count": len(tools),
            "tools": [t.name for t in tools],
            "max_iterations": max_iterations,
        }
        if manifest:
            info["version"] = getattr(manifest, "version", "1.0.0")
            info["display_name"] = getattr(manifest, "display_name", "")
            info["fallback_capability"] = getattr(manifest, "fallback_capability", "")
            info["aliases"] = getattr(manifest, "agent_aliases", [])
        return info


# Module-level convenience functions
infer_agent_name = AgentValidator.infer_name
validate_agent_configuration = AgentValidator.validate_configuration
describe_agent = AgentValidator.describe

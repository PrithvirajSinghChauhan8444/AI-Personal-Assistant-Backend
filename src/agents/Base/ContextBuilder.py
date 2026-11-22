"""Context construction and validation for BaseAgent turns."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from src.agents.contracts import AgentContext, AgentType, ToolDefinition


class ContextBuilder:
    """Constructs and validates AgentContext instances."""

    @staticmethod
    def validate_identifiers(session_id: str, turn_id: str) -> None:
        """Validates that session and turn identifiers are non-empty strings."""
        if not session_id or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not turn_id or not turn_id.strip():
            raise ValueError("turn_id must be a non-empty string")

    @classmethod
    def build(
        cls,
        session_id: str,
        turn_id: str,
        prompt: str,
        agent_type: Union[AgentType, str],
        system_prompt: str,
        tools: List[ToolDefinition],
        history: Optional[List[Dict[str, Any]]] = None,
        max_iterations: int = 10,
        base_metadata: Optional[Dict[str, Any]] = None,
        override_metadata: Optional[Dict[str, Any]] = None,
        local_handlers: Optional[Dict[str, Any]] = None,
    ) -> AgentContext:
        """Validates identifiers and packages execution parameters into an AgentContext."""
        cls.validate_identifiers(session_id, turn_id)

        merged_metadata = dict(base_metadata or {})
        if override_metadata:
            merged_metadata.update(override_metadata)

        handlers = dict(local_handlers or {})
        if "local_handlers" in merged_metadata and not handlers:
            handlers = merged_metadata["local_handlers"]

        return AgentContext(
            session_id=session_id.strip(),
            turn_id=turn_id.strip(),
            agent_type=agent_type,
            user_prompt=prompt,
            system_prompt=system_prompt,
            conversation_history=history or [],
            available_tools=tools,
            max_iterations=max_iterations,
            metadata=merged_metadata,
            local_handlers=handlers,
        )

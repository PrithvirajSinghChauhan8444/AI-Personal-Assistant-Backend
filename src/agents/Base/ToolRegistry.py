"""Tool registry and risk management for BaseAgent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.agents.contracts import ToolDefinition

RISK_ORDER: Dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


class ToolRegistry:
    """Manages tool registration, lookup, risk filtering, and schema serialization."""

    def __init__(self, initial_tools: Optional[Sequence[ToolDefinition]] = None) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        if initial_tools:
            self.register_all(initial_tools)

    def validate(self) -> None:
        """Validates that all registered tools have valid non-empty names."""
        for tool in self._tools.values():
            if not tool.name or not tool.name.strip():
                raise ValueError(f"Encountered tool with empty name in registry: {tool}")

    def register(self, tool: ToolDefinition) -> None:
        """Registers a tool definition. Raises TypeError if invalid."""
        if not isinstance(tool, ToolDefinition):
            raise TypeError(f"Expected ToolDefinition, got {type(tool).__name__}")
        self._tools[tool.name] = tool

    def register_all(self, tools: Sequence[ToolDefinition]) -> None:
        """Registers multiple tool definitions."""
        for tool in tools:
            self.register(tool)

    def unregister(self, tool_name: str) -> bool:
        """Removes a tool by name. Returns True if removed, False otherwise."""
        return self._tools.pop(tool_name, None) is not None

    def get(self, tool_name: str) -> Optional[ToolDefinition]:
        """Retrieves a tool definition by name."""
        return self._tools.get(tool_name)

    def has(self, tool_name: str) -> bool:
        """Checks if a tool is registered."""
        return tool_name in self._tools

    def has_tool(self, tool_name: str) -> bool:
        """Checks if a tool is registered (alias for has)."""
        return self.has(tool_name)

    def all(self) -> List[ToolDefinition]:
        """Returns a list of all registered tool definitions."""
        return list(self._tools.values())

    def clear(self) -> None:
        """Clears all registered tools."""
        self._tools.clear()

    def filter_by_risk(self, max_risk: str = "HIGH") -> List[ToolDefinition]:
        """Filters tools whose risk level is at or below max_risk (LOW <= MEDIUM <= HIGH)."""
        ceiling = RISK_ORDER.get(max_risk.upper(), 3)
        return [
            tool
            for tool in self._tools.values()
            if RISK_ORDER.get(tool.risk.upper(), 1) <= ceiling
        ]

    def filter_tools_by_risk(self, max_risk: str = "HIGH") -> List[ToolDefinition]:
        """Alias for filter_by_risk."""
        return self.filter_by_risk(max_risk)

    def to_schemas(self) -> List[Dict[str, Any]]:
        """Converts registered tools into OpenAI-compatible function-calling schemas."""
        return [tool.to_dict() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())

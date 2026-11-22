"""Data contracts, protocols, and result types for the Tool Dispatcher subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.agents.contracts import ToolCallIntent, ToolCallResult, ToolExecutionDomain


@runtime_checkable
class MCPClientProtocol(Protocol):
    """Protocol for Model Context Protocol (MCP) clients."""

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None,
    ) -> ToolCallResult:
        """Executes a single tool on the MCP bridge."""
        ...


@dataclass
class ToolTurnExecutionResult:
    """Consolidated outcome of executing tool calls initiated in an agent turn."""

    intents: List[ToolCallIntent] = field(default_factory=list)
    results: List[ToolCallResult] = field(default_factory=list)
    tool_messages: List[Dict[str, Any]] = field(default_factory=list)
    has_errors: bool = False
    elapsed_ms: int = 0

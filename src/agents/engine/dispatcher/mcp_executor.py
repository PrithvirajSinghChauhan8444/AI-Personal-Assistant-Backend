"""MCP (Model Context Protocol) tool executor for remote JSON-RPC bridges."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Optional, Union

from src.agents.contracts import AgentContext, ToolCallIntent, ToolCallResult
from src.agents.engine.dispatcher.types import MCPClientProtocol


class MCPToolExecutor:
    """Executes tools through Model Context Protocol (MCP) clients."""

    def __init__(
        self,
        mcp_client: Optional[Union[MCPClientProtocol, Callable[..., Any]]] = None,
    ) -> None:
        self.mcp_client = mcp_client

    def set_client(
        self, client: Union[MCPClientProtocol, Callable[..., Any]]
    ) -> MCPToolExecutor:
        """Sets or replaces the MCP client bridge."""
        self.mcp_client = client
        return self

    @property
    def has_client(self) -> bool:
        """Reports whether an MCP client is configured."""
        return self.mcp_client is not None

    async def execute(
        self, intent: ToolCallIntent, ctx: Optional[AgentContext] = None
    ) -> ToolCallResult:
        """Dispatches tool execution to the connected MCP client."""
        if not self.has_client:
            return self._error_result(
                intent.call_id, f"MCP Error: no MCP client configured for '{intent.tool_name}'"
            )
        try:
            if hasattr(self.mcp_client, "execute_tool"):
                return await self.mcp_client.execute_tool(  # type: ignore[union-attr]
                    intent.tool_name, intent.arguments, intent.call_id
                )
            if callable(self.mcp_client):
                return await self._run_callable_client(intent)
            return self._error_result(
                intent.call_id, f"Invalid MCP client type: {type(self.mcp_client).__name__}"
            )
        except Exception as exc:
            return self._error_result(
                intent.call_id, f"MCP bridge error in '{intent.tool_name}': {exc}"
            )

    async def _run_callable_client(self, intent: ToolCallIntent) -> ToolCallResult:
        res = self.mcp_client(intent.tool_name, intent.arguments, intent.call_id)  # type: ignore[call-arg]
        if inspect.isawaitable(res):
            res = await res
        if isinstance(res, ToolCallResult):
            return res
        return ToolCallResult(call_id=intent.call_id, output=str(res), is_error=False)

    def _error_result(self, call_id: str, message: str) -> ToolCallResult:
        return ToolCallResult(call_id=call_id, output=message, is_error=True)

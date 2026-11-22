"""In-process Python tool executor for local callable handlers and memory engines."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Optional

from src.agents.contracts import (
    AgentContext,
    MemoryEngineProtocol,
    ToolCallIntent,
    ToolCallResult,
)


class PythonToolExecutor:
    """Executes Python-local tools in-process with zero IPC latency."""

    def __init__(
        self,
        local_handlers: Optional[Dict[str, Callable[..., Any]]] = None,
        memory_engine: Optional[MemoryEngineProtocol] = None,
    ) -> None:
        self.local_handlers: Dict[str, Callable[..., Any]] = dict(local_handlers or {})
        self.memory_engine = memory_engine

    def register_handler(self, name: str, handler: Callable[..., Any]) -> PythonToolExecutor:
        """Registers an in-process callable for a specific tool name."""
        self.local_handlers[name] = handler
        return self

    def unregister_handler(self, name: str) -> bool:
        """Removes an in-process callable handler."""
        return self.local_handlers.pop(name, None) is not None

    def has_handler(self, tool_name: str, ctx: Optional[AgentContext] = None) -> bool:
        """Checks if a local Python callable handler exists for the tool."""
        if tool_name in self.local_handlers:
            return True
        if ctx and ctx.local_handlers and tool_name in ctx.local_handlers:
            return True
        return False

    def is_memory_tool(self, tool_name: str) -> bool:
        """Checks if the tool is handled by the Python MemoryEngine."""
        if self.memory_engine and self.memory_engine.is_memory_tool(tool_name):
            return True
        return tool_name.startswith("memory_")

    async def execute(
        self, intent: ToolCallIntent, ctx: Optional[AgentContext] = None
    ) -> ToolCallResult:
        """Executes a local Python function or memory tool."""
        handler = self._resolve_handler(intent.tool_name, ctx)
        if handler:
            return await self._run_callable(intent, handler)
        if self.is_memory_tool(intent.tool_name):
            return await self._execute_memory_tool(intent, ctx)
        return ToolCallResult(
            call_id=intent.call_id,
            output=f"Error: no Python handler registered for '{intent.tool_name}'",
            is_error=True,
        )

    def _resolve_handler(
        self, tool_name: str, ctx: Optional[AgentContext]
    ) -> Optional[Callable[..., Any]]:
        if tool_name in self.local_handlers:
            return self.local_handlers[tool_name]
        if ctx and ctx.local_handlers and tool_name in ctx.local_handlers:
            return ctx.local_handlers[tool_name]
        return None

    async def _run_callable(
        self, intent: ToolCallIntent, handler: Callable[..., Any]
    ) -> ToolCallResult:
        try:
            if inspect.iscoroutinefunction(handler):
                res = await handler(**intent.arguments)
            else:
                res = handler(**intent.arguments)
            return ToolCallResult(call_id=intent.call_id, output=str(res), is_error=False)
        except Exception as exc:
            return ToolCallResult(
                call_id=intent.call_id,
                output=f"Python execution error in '{intent.tool_name}': {exc}",
                is_error=True,
            )

    async def _execute_memory_tool(
        self, intent: ToolCallIntent, ctx: Optional[AgentContext]
    ) -> ToolCallResult:
        if not self.memory_engine:
            return ToolCallResult(
                call_id=intent.call_id,
                output=f"Memory engine unavailable for '{intent.tool_name}'",
                is_error=True,
            )
        try:
            sess_id = ctx.session_id if ctx else None
            t_id = ctx.turn_id if ctx else None
            output = await self._invoke_memory_engine(intent, sess_id, t_id)
            return ToolCallResult(call_id=intent.call_id, output=str(output), is_error=False)
        except Exception as exc:
            return ToolCallResult(
                call_id=intent.call_id,
                output=f"Memory tool error in '{intent.tool_name}': {exc}",
                is_error=True,
            )

    async def _invoke_memory_engine(
        self, intent: ToolCallIntent, session_id: Optional[str], turn_id: Optional[str]
    ) -> Any:
        try:
            return await self.memory_engine.execute_tool(  # type: ignore[union-attr]
                intent.tool_name, intent.arguments, session_id=session_id, turn_id=turn_id
            )
        except TypeError:
            return await self.memory_engine.execute_tool(  # type: ignore[union-attr]
                intent.tool_name, intent.arguments
            )

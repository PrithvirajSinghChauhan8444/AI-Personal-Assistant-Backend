"""Unified ToolDispatcher coordinating extraction, domain routing, and polyglot execution."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from src.agents.contracts import (
    AgentContext,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolCallIntent,
    ToolCallResult,
    ToolDefinition,
    ToolExecutionDomain,
)
from src.agents.engine.dispatcher.extractor import IntentExtractor
from src.agents.engine.dispatcher.go_executor import GoToolExecutor
from src.agents.engine.dispatcher.mcp_executor import MCPToolExecutor
from src.agents.engine.dispatcher.python_executor import PythonToolExecutor
from src.agents.engine.dispatcher.router import DomainRouter
from src.agents.engine.dispatcher.types import (
    MCPClientProtocol,
    ToolTurnExecutionResult,
)


class ToolDispatcher:
    """Pluggable polyglot tool dispatcher selecting Python, Go IPC, or MCP routes."""

    def __init__(
        self,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        mcp_client: Optional[Union[MCPClientProtocol, Callable[..., Any]]] = None,
        local_handlers: Optional[Dict[str, Callable[..., Any]]] = None,
        domain_overrides: Optional[Dict[str, Union[ToolExecutionDomain, str]]] = None,
        go_subprocess_fallback: bool = False,
        tool_definitions: Optional[Dict[str, ToolDefinition]] = None,
        tools: Optional[Sequence[ToolDefinition]] = None,
        extractor: Optional[IntentExtractor] = None,
        router: Optional[DomainRouter] = None,
        python_executor: Optional[PythonToolExecutor] = None,
        go_executor: Optional[GoToolExecutor] = None,
        mcp_executor: Optional[MCPToolExecutor] = None,
    ) -> None:
        merged_tools: Dict[str, ToolDefinition] = dict(tool_definitions or {})
        if tools:
            for t in tools:
                merged_tools[t.name] = t

        self.extractor = extractor or IntentExtractor()
        self.router = router or DomainRouter(
            domain_overrides=domain_overrides,
            tool_definitions=merged_tools,
        )
        self.python_executor = python_executor or PythonToolExecutor(
            local_handlers=local_handlers,
            memory_engine=memory_engine,
        )
        self.go_executor = go_executor or GoToolExecutor(
            pipe_emitter=pipe_emitter,
            pipe_reader=pipe_reader,
            subprocess_fallback=go_subprocess_fallback,
        )
        self.mcp_executor = mcp_executor or MCPToolExecutor(
            mcp_client=mcp_client,
        )

    # Delegation properties for backward compatibility
    @property
    def local_handlers(self) -> Dict[str, Callable[..., Any]]:
        return self.python_executor.local_handlers

    @property
    def memory_engine(self) -> Optional[MemoryEngineProtocol]:
        return self.python_executor.memory_engine

    @property
    def mcp_client(self) -> Optional[Union[MCPClientProtocol, Callable[..., Any]]]:
        return self.mcp_executor.mcp_client

    @property
    def domain_overrides(self) -> Dict[str, ToolExecutionDomain]:
        return self.router.domain_overrides

    @property
    def tool_definitions(self) -> Dict[str, ToolDefinition]:
        return self.router.tool_definitions

    @property
    def pipe_emitter(self) -> Optional[PipeEmitterProtocol]:
        return self.go_executor.pipe_emitter

    @property
    def pipe_reader(self) -> Optional[PipeReaderProtocol]:
        return self.go_executor.pipe_reader

    # Fluent configuration API
    def register_handler(self, name: str, handler: Callable[..., Any]) -> ToolDispatcher:
        """Registers an in-process Python callable handler."""
        self.python_executor.register_handler(name, handler)
        return self

    def register_tool_definition(self, tool: ToolDefinition) -> ToolDispatcher:
        """Registers tool metadata definition into the dispatcher catalog."""
        self.router.register_tool_definition(tool)
        return self

    def unregister_tool(self, tool_name: str) -> bool:
        """Removes a tool definition and its local handler if present."""
        removed_tool = self.router.unregister_tool_definition(tool_name)
        removed_handler = self.python_executor.unregister_handler(tool_name)
        return removed_tool or removed_handler

    def get_registered_tools(self) -> Dict[str, ToolDefinition]:
        """Returns registered tool definitions dictionary."""
        return dict(self.router.tool_definitions)

    def set_domain_override(
        self, tool_name: str, domain: Union[ToolExecutionDomain, str]
    ) -> ToolDispatcher:
        """Explicitly pins a tool to a specific execution domain."""
        self.router.set_domain_override(tool_name, domain)
        return self

    def set_mcp_client(
        self, client: Union[MCPClientProtocol, Callable[..., Any]]
    ) -> ToolDispatcher:
        """Configures or replaces the MCP client bridge."""
        self.mcp_executor.set_client(client)
        return self

    # Core routing & extraction
    def determine_domain(
        self, tool_name: str, ctx: Optional[AgentContext] = None
    ) -> ToolExecutionDomain:
        """Resolves the execution route (Python local, Go IPC, or MCP)."""
        return self.router.determine_domain(
            tool_name=tool_name,
            ctx=ctx,
            has_local_handler=self.python_executor.has_handler(tool_name, ctx),
            is_memory_tool=self.python_executor.is_memory_tool(tool_name),
            has_mcp_client=self.mcp_executor.has_client,
            has_pipe_emitter=self.go_executor.has_ipc,
        )

    def extract_tool_intents(self, response: Any) -> List[ToolCallIntent]:
        """Extracts standardized ToolCallIntents from previous turn output."""
        return self.extractor.extract(response)

    # Tool Execution
    async def execute_intent(
        self, intent: ToolCallIntent, ctx: Optional[AgentContext] = None
    ) -> ToolCallResult:
        """Executes a single tool intent via its optimal domain path."""
        domain = self.determine_domain(intent.tool_name, ctx)
        if domain == ToolExecutionDomain.PYTHON_LOCAL:
            return await self.python_executor.execute(intent, ctx)
        if domain == ToolExecutionDomain.MCP_BRIDGE:
            return await self.mcp_executor.execute(intent, ctx)
        return await self.go_executor.execute(intent, ctx)

    async def execute_intents(
        self, intents: Sequence[ToolCallIntent], ctx: Optional[AgentContext] = None
    ) -> List[ToolCallResult]:
        """Executes a sequence of tool intents in order."""
        results: List[ToolCallResult] = []
        for intent in intents:
            result = await self.execute_intent(intent, ctx)
            results.append(result)
        return results

    async def execute_turn_response(
        self,
        response: Any,
        ctx: Optional[AgentContext] = None,
        turn_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ToolTurnExecutionResult:
        """Parses tool calls from an agent's turn response, executes them, and formats messages."""
        start_time = time.perf_counter()
        intents = self.extract_tool_intents(response)
        if not intents:
            return ToolTurnExecutionResult()

        effective_ctx = self._ensure_context(ctx, turn_id, session_id)
        results = await self.execute_intents(intents, effective_ctx)
        tool_messages = self.format_tool_messages(results)
        has_errors = any(r.is_error for r in results)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return ToolTurnExecutionResult(
            intents=intents,
            results=results,
            tool_messages=tool_messages,
            has_errors=has_errors,
            elapsed_ms=elapsed_ms,
        )

    def _ensure_context(
        self,
        ctx: Optional[AgentContext],
        turn_id: Optional[str],
        session_id: Optional[str],
    ) -> AgentContext:
        if ctx is not None:
            return ctx
        return AgentContext(
            session_id=session_id or "default_session",
            turn_id=turn_id or "default_turn",
            agent_type="standalone",
            user_prompt="",
            system_prompt="",
        )

    @staticmethod
    def format_tool_messages(results: Sequence[ToolCallResult]) -> List[Dict[str, Any]]:
        """Transforms ToolCallResults into standard OpenAI tool response message format."""
        return [
            {
                "role": "tool",
                "tool_call_id": res.call_id,
                "content": res.output,
            }
            for res in results
        ]

    @staticmethod
    def apply_to_conversation(
        messages: List[Dict[str, Any]], execution_result: ToolTurnExecutionResult
    ) -> None:
        """Appends tool execution messages directly into a conversation history list."""
        messages.extend(execution_result.tool_messages)

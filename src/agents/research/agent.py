"""ResearchAgent implementation using the standard BaseAgent architecture.

Dynamically registers all tools (Go-native, Python-local, and MCP) from `AgentTools/tools.py`
and coordinates execution via the modular Polyglot ToolDispatcher.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

from src.agents.Base import BaseAgent
from src.agents.contracts import (
    AgentContext,
    AgentType,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolCallIntent,
    ToolCallResult,
    ToolDefinition,
)
from src.agents.engine.dispatcher import (
    MCPClientProtocol,
    ToolDispatcher,
    ToolTurnExecutionResult,
)
from src.agents.research.AgentTools import (
    enrich_prompt_with_tools,
    get_research_local_handlers,
    get_research_tool_definitions,
)
from src.agents.research.prompts import get_research_prompt
from src.models.base import BaseLLMClient


class ResearchAgent(BaseAgent):
    """Specialized worker for deep research, web searches, fact-checking, and memory notes."""

    def __init__(
        self,
        model_client: BaseLLMClient,
        custom_tools: Optional[List[ToolDefinition]] = None,
        custom_handlers: Optional[Dict[str, Callable]] = None,
        auto_enrich_prompt: bool = False,
        tool_dispatcher: Optional[ToolDispatcher] = None,
        mcp_client: Optional[Union[MCPClientProtocol, Callable[..., Any]]] = None,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
        **kwargs: Any,
    ) -> None:
        tools = custom_tools if custom_tools is not None else get_research_tool_definitions()

        self.local_handlers: Dict[str, Callable] = dict(get_research_local_handlers())
        if custom_handlers:
            self.local_handlers.update(custom_handlers)

        self.tool_dispatcher: ToolDispatcher = tool_dispatcher or ToolDispatcher(
            pipe_emitter=pipe_emitter,
            pipe_reader=pipe_reader,
            memory_engine=memory_engine,
            mcp_client=mcp_client,
            local_handlers=self.local_handlers,
        )
        self._sync_dispatcher_tools(tools)

        self._base_prompt = get_research_prompt()
        system_prompt = (
            enrich_prompt_with_tools(self._base_prompt, tools)
            if auto_enrich_prompt
            else self._base_prompt
        )

        super().__init__(
            model_client=model_client,
            agent_type=AgentType.RESEARCH,
            system_prompt=system_prompt,
            tools=tools,
            memory_engine=memory_engine,
            tool_dispatcher=self.tool_dispatcher,
            local_handlers=self.local_handlers,
            **kwargs,
        )

    def _sync_dispatcher_tools(self, tools: List[ToolDefinition]) -> None:
        """Registers research tool definitions and local handlers into dispatcher."""
        for tool in tools:
            self.tool_dispatcher.register_tool_definition(tool)
        for name, handler in self.local_handlers.items():
            self.tool_dispatcher.register_handler(name, handler)

    def get_base_prompt(self) -> str:
        """Returns the unmodified base system prompt."""
        return self._base_prompt

    def get_enriched_prompt(self) -> str:
        """Returns the system prompt dynamically enriched with all active tool capabilities."""
        return enrich_prompt_with_tools(self._base_prompt, self.get_tools())

    def create_context(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        max_iterations: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentContext:
        """Builds turn context, injecting enriched prompt and local tool handlers."""
        ctx = super().create_context(
            session_id=session_id,
            turn_id=turn_id,
            prompt=prompt,
            history=history,
            max_iterations=max_iterations,
            metadata=metadata,
        )
        ctx.system_prompt = self.get_enriched_prompt()
        return ctx

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None,
        ctx: Optional[AgentContext] = None,
    ) -> ToolCallResult:
        """Directly invokes a single tool via the agent's ToolDispatcher."""
        intent = ToolCallIntent(
            call_id=call_id or f"call_{tool_name}",
            tool_name=tool_name,
            arguments=arguments,
        )
        return await self.tool_dispatcher.execute_intent(intent, ctx)

    async def execute_turn_response(
        self,
        response: Any,
        ctx: Optional[AgentContext] = None,
        turn_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ToolTurnExecutionResult:
        """Executes all tool calls parsed from an agent's turn response."""
        return await self.tool_dispatcher.execute_turn_response(
            response=response,
            ctx=ctx,
            turn_id=turn_id,
            session_id=session_id,
        )

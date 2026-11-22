"""ResearchAgent implementation using the standard BaseAgent architecture.

Provides the specialized worker for deep research, web searches, fact-checking,
and memory notes using static tool definitions and local handlers.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.agents.Base import BaseAgent
from src.agents.contracts import AgentType, ToolDefinition
from src.agents.engine.tool_dispatcher import ToolDispatcher
from src.agents.research.AgentTools import (
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
        tool_dispatcher: Optional[ToolDispatcher] = None,
        **kwargs: Any,
    ) -> None:
        tools = custom_tools if custom_tools is not None else get_research_tool_definitions()
        local_handlers = dict(get_research_local_handlers())
        if custom_handlers:
            local_handlers.update(custom_handlers)

        super().__init__(
            model_client=model_client,
            agent_type=AgentType.RESEARCH,
            system_prompt=get_research_prompt(),
            tools=tools,
            local_handlers=local_handlers,
            tool_dispatcher=tool_dispatcher,
            **kwargs,
        )

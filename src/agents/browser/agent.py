"""BrowserAgent implementation."""

from typing import Any, Dict, List, Optional

from src.agents.browser.prompts import BROWSER_AGENT_PROMPT, get_browser_prompt
from src.agents.browser.tools import BROWSER_TOOLS
from src.agents.contracts import (
    AgentContext,
    AgentTurnResult,
    AgentType,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
)
from src.agents.engine.react_engine import run_worker_agent
from src.models.base import BaseLLMClient


class BrowserAgent:
    """Specialized worker for Playwright browser automation, navigation, and visual inspection."""

    def __init__(self, model_client: BaseLLMClient) -> None:
        self.model_client = model_client
        self.agent_type = AgentType.BROWSER
        self.system_prompt = get_browser_prompt()
        self.tools = BROWSER_TOOLS

    async def execute_turn(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        max_iterations: int = 10,
    ) -> AgentTurnResult:
        """Runs an autonomous execution turn for the browser worker."""
        ctx = AgentContext(
            session_id=session_id,
            turn_id=turn_id,
            agent_type=self.agent_type,
            user_prompt=prompt,
            system_prompt=self.system_prompt,
            conversation_history=history or [],
            available_tools=self.tools,
            max_iterations=max_iterations,
        )

        return await run_worker_agent(
            ctx=ctx,
            model_client=self.model_client,
            memory_engine=memory_engine,
            pipe_emitter=pipe_emitter,
            pipe_reader=pipe_reader,
        )

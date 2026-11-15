"""SummarizerAgent implementation."""

from typing import Any, Dict, List, Optional

from src.agents.contracts import (
    AgentContext,
    AgentTurnResult,
    AgentType,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
)
from src.agents.engine.react_engine import run_worker_agent
from src.agents.summarizer.prompts import get_summarizer_prompt
from src.agents.summarizer.tools import SUMMARIZER_TOOLS
from src.models.base import BaseLLMClient


class SummarizerAgent:
    """Specialist worker for synthesizing subtask outputs into clean, human-readable final responses."""

    def __init__(self, model_client: BaseLLMClient) -> None:
        self.model_client = model_client
        self.agent_name = "summarizer"
        self.system_prompt = get_summarizer_prompt()
        self.tools = SUMMARIZER_TOOLS

    async def execute_turn(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        max_iterations: int = 5,
    ) -> AgentTurnResult:
        """Executes a cognitive turn to synthesize task outputs into a human-readable final message."""
        context = AgentContext(
            session_id=session_id,
            turn_id=turn_id,
            agent_type=self.agent_name,
            user_prompt=prompt,
            system_prompt=self.system_prompt,
            conversation_history=history or [],
            available_tools=self.tools,
            max_iterations=max_iterations,
        )

        return await run_worker_agent(
            ctx=context,
            model_client=self.model_client,
            memory_engine=memory_engine,
            pipe_emitter=pipe_emitter,
            pipe_reader=pipe_reader,
        )

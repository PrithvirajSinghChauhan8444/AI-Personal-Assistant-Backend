"""MemoryAgent implementation."""

import sys
from typing import Any, Dict, List, Optional
import uuid

from src.agents.contracts import (
    AgentContext,
    AgentTurnResult,
    AgentType,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolDefinition,
)
from src.agents.engine.react_engine import run_worker_agent
from src.agents.memory.prompts import (
    MEMORY_AGENT_PROMPT,
    get_memory_prompt,
    get_memory_worker_prompt,
)
from src.agents.memory.tools import MEMORY_WORKER_TOOLS
from src.models.base import BaseLLMClient


class MemoryAgent:
    """Specialized worker for personal memory recall, fact archival, and profile management."""

    def __init__(
        self,
        model_client: BaseLLMClient,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        tools: Optional[List[ToolDefinition]] = None,
    ) -> None:
        self.model_client = model_client
        self.agent_type = AgentType.MEMORY
        self.system_prompt = get_memory_prompt()
        self.tools = tools or MEMORY_WORKER_TOOLS
        self._memory_engine = memory_engine

    @property
    def memory_engine(self) -> MemoryEngineProtocol:
        if self._memory_engine is None:
            from src.memory.engine import MemoryEngine
            self._memory_engine = MemoryEngine()
        return self._memory_engine

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
        """Runs an autonomous execution turn for the memory worker."""
        active_memory = memory_engine or self.memory_engine

        grounding_context = ""
        if active_memory and hasattr(active_memory, "build_grounding_prompt"):
            grounding_context = active_memory.build_grounding_prompt()

        full_system_prompt = f"{self.system_prompt}\n\n{grounding_context}".strip()

        ctx = AgentContext(
            session_id=session_id,
            turn_id=turn_id,
            agent_type=self.agent_type,
            user_prompt=prompt,
            system_prompt=full_system_prompt,
            conversation_history=history or [],
            available_tools=self.tools,
            max_iterations=max_iterations,
        )

        return await run_worker_agent(
            ctx=ctx,
            model_client=self.model_client,
            memory_engine=active_memory,
            pipe_emitter=pipe_emitter,
            pipe_reader=pipe_reader,
        )

    async def run_standalone(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        verbose: bool = True,
        max_iterations: int = 10,
    ) -> AgentTurnResult:
        """Executes a standalone turn directly in terminal without Go or external bridge."""
        from src.agents.memory.__main__ import StandaloneConsoleEmitter

        session_id = f"standalone_{uuid.uuid4().hex[:8]}"
        turn_id = f"turn_{uuid.uuid4().hex[:8]}"
        emitter = StandaloneConsoleEmitter(verbose=verbose)

        result = await self.execute_turn(
            session_id=session_id,
            turn_id=turn_id,
            prompt=prompt,
            history=history,
            pipe_emitter=emitter,
            pipe_reader=emitter,
            memory_engine=self.memory_engine,
            max_iterations=max_iterations,
        )

        if not emitter.has_streamed_tokens and result.final_response:
            sys.stdout.write(f"{result.final_response}\n")
            sys.stdout.flush()
        else:
            emitter.flush()

        return result

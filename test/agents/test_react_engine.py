"""Tests for Framework-Free Async ReAct Engine."""

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional
import pytest

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
from src.agents.engine.react_engine import ReActEngine
from src.models.base import BaseLLMClient
from src.models.types import StreamChunk, ToolCallChunk


class MockEmitter(PipeEmitterProtocol):
    def __init__(self) -> None:
        self.thoughts: List[str] = []
        self.tokens: List[str] = []
        self.tool_calls: List[ToolCallIntent] = []
        self.statuses: List[str] = []

    async def emit_thought(self, turn_id: str, agent_name: str, thought: str) -> None:
        self.thoughts.append(thought)

    async def emit_token(self, turn_id: str, agent_name: str, token: str) -> None:
        self.tokens.append(token)

    async def emit_tool_call(self, turn_id: str, intent: ToolCallIntent) -> None:
        self.tool_calls.append(intent)

    async def emit_status(self, turn_id: str, agent_name: str, status_msg: str) -> None:
        self.statuses.append(status_msg)


class MockReader(PipeReaderProtocol):
    def __init__(self, responses: Optional[List[ToolCallResult]] = None) -> None:
        self.responses = responses or []

    async def wait_for_tool_results(self, turn_id: str, expected_count: int) -> List[ToolCallResult]:
        if self.responses:
            res = self.responses[:expected_count]
            self.responses = self.responses[expected_count:]
            return res
        return [
            ToolCallResult(call_id=f"call_{i}", output="ok", is_error=False)
            for i in range(expected_count)
        ]


class MockMemoryEngine(MemoryEngineProtocol):
    def __init__(self) -> None:
        self.executed_tools: List[tuple[str, Dict[str, Any]]] = []

    def is_memory_tool(self, tool_name: str) -> bool:
        return tool_name.startswith("memory_")

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        self.executed_tools.append((tool_name, arguments))
        return "memory fact stored successfully"


class ScriptedLLMClient(BaseLLMClient):
    """Yields pre-scripted StreamChunks for testing the ReAct loop."""

    def __init__(self, turns: List[List[StreamChunk]]) -> None:
        super().__init__(model_name="scripted-test-llm")
        self.turns = list(turns)
        self.call_count = 0

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        if self.call_count < len(self.turns):
            chunks = self.turns[self.call_count]
            self.call_count += 1
            for c in chunks:
                yield c
        else:
            yield StreamChunk(text_delta="Completed.")


@pytest.mark.asyncio
async def test_text_only_turn() -> None:
    llm = ScriptedLLMClient([
        [
            StreamChunk(thought="Thinking..."),
            StreamChunk(text_delta="Hello "),
            StreamChunk(text_delta="world!"),
        ]
    ])
    emitter = MockEmitter()
    engine = ReActEngine(model_client=llm, pipe_emitter=emitter)

    ctx = AgentContext(
        session_id="s1",
        turn_id="t1",
        agent_type=AgentType.SYSTEM,
        user_prompt="Hi",
        system_prompt="Test",
    )

    result = await engine.run(ctx)
    assert result.status == "success"
    assert result.final_response == "Hello world!"
    assert result.iterations_used == 1
    assert result.tool_calls_executed == 0
    assert emitter.thoughts == ["Thinking..."]
    assert "".join(emitter.tokens) == "Hello world!"


@pytest.mark.asyncio
async def test_tool_call_and_resolution() -> None:
    llm = ScriptedLLMClient([
        # Turn 1: request tool call
        [
            StreamChunk(thought="Need to check status"),
            StreamChunk(
                tool_calls=[
                    ToolCallChunk(
                        call_id="call_01",
                        tool_name="git_status",
                        arguments_json='{"repo_path": "."}',
                    )
                ]
            ),
        ],
        # Turn 2: formulate answer
        [
            StreamChunk(text_delta="Branch is clean."),
        ],
    ])

    emitter = MockEmitter()
    reader = MockReader([
        ToolCallResult(call_id="call_01", output="## main...origin/main (clean)", is_error=False)
    ])

    tool_def = ToolDefinition(name="git_status", description="Git status", parameters={})
    ctx = AgentContext(
        session_id="s1",
        turn_id="t1",
        agent_type=AgentType.SYSTEM,
        user_prompt="Check git",
        system_prompt="Test",
        available_tools=[tool_def],
    )

    engine = ReActEngine(model_client=llm, pipe_emitter=emitter, pipe_reader=reader)
    result = await engine.run(ctx)

    assert result.status == "success"
    assert result.final_response == "Branch is clean."
    assert result.iterations_used == 2
    assert result.tool_calls_executed == 1
    assert len(emitter.tool_calls) == 1
    assert emitter.tool_calls[0].tool_name == "git_status"


@pytest.mark.asyncio
async def test_local_memory_tool_direct_execution() -> None:
    llm = ScriptedLLMClient([
        # Turn 1: invoke memory tool
        [
            StreamChunk(
                tool_calls=[
                    ToolCallChunk(
                        call_id="mem_01",
                        tool_name="memory_store_fact",
                        arguments_json='{"fact": "User prefers Linux"}',
                    )
                ]
            ),
        ],
        # Turn 2: answer
        [
            StreamChunk(text_delta="Saved to memory."),
        ],
    ])

    emitter = MockEmitter()
    reader = MockReader([])
    memory_engine = MockMemoryEngine()

    ctx = AgentContext(
        session_id="s1",
        turn_id="t1",
        agent_type=AgentType.RESEARCH,
        user_prompt="Remember I like Linux",
        system_prompt="Test",
    )

    engine = ReActEngine(
        model_client=llm,
        memory_engine=memory_engine,
        pipe_emitter=emitter,
        pipe_reader=reader,
    )

    result = await engine.run(ctx)
    assert result.status == "success"
    assert result.final_response == "Saved to memory."
    assert len(memory_engine.executed_tools) == 1
    assert memory_engine.executed_tools[0][0] == "memory_store_fact"
    # Remote pipe should NOT have received local memory tool
    assert len(emitter.tool_calls) == 0


@pytest.mark.asyncio
async def test_max_iterations_ceiling() -> None:
    # Model endlessly requests tools
    infinite_tool_turn = [
        StreamChunk(
            tool_calls=[
                ToolCallChunk(call_id=f"call_{i}", tool_name="sys_ps", arguments_json="{}")
            ]
        )
        for i in range(15)
    ]

    llm = ScriptedLLMClient([[StreamChunk(tool_calls=[ToolCallChunk(call_id=f"c_{i}", tool_name="sys_ps", arguments_json="{}")])] for i in range(15)])
    reader = MockReader()

    ctx = AgentContext(
        session_id="s1",
        turn_id="t1",
        agent_type=AgentType.SYSTEM,
        user_prompt="Run forever",
        system_prompt="Test",
        max_iterations=5,
    )

    engine = ReActEngine(model_client=llm, pipe_reader=reader)
    result = await engine.run(ctx)

    assert result.status == "max_iterations_reached"
    assert result.iterations_used == 5

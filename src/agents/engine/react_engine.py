"""Framework-Free Async ReAct Engine for Layer 6 Agents."""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

from src.agents.contracts import (
    AgentContext,
    AgentTurnResult,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolCallIntent,
    ToolCallResult,
)
from src.models.base import BaseLLMClient
from src.models.types import ToolCallChunk


class ReActEngine:
    """Orchestrates an asynchronous ReAct loop with strict iteration guardrails."""

    def __init__(
        self,
        model_client: BaseLLMClient,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
    ) -> None:
        self.model_client = model_client
        self.memory_engine = memory_engine
        self.pipe_emitter = pipe_emitter
        self.pipe_reader = pipe_reader

    async def run(self, ctx: AgentContext) -> AgentTurnResult:
        """Executes the autonomous reasoning and action loop for a given context."""
        messages = ctx.conversation_history
        messages.append({"role": "user", "content": ctx.user_prompt})

        tool_schemas = [t.to_dict() for t in ctx.available_tools] if ctx.available_tools else None
        iterations = 0
        total_tool_calls = 0
        latest_text = ""

        try:
            while iterations < ctx.max_iterations:
                iterations += 1

                step_text, tool_chunks = await self._stream_model_turn(ctx, messages, tool_schemas)
                if step_text:
                    latest_text = step_text

                if not tool_chunks:
                    return AgentTurnResult(
                        status="success",
                        final_response=latest_text,
                        iterations_used=iterations,
                        tool_calls_executed=total_tool_calls,
                    )

                tool_intents = self._parse_tool_intents(tool_chunks)
                total_tool_calls += len(tool_intents)

                self._record_assistant_turn(messages, step_text, tool_intents)
                await self._execute_and_record_tools(ctx, messages, tool_intents)

            return AgentTurnResult(
                status="max_iterations_reached",
                final_response=latest_text,
                iterations_used=iterations,
                tool_calls_executed=total_tool_calls,
            )

        except asyncio.CancelledError:
            return AgentTurnResult(
                status="cancelled",
                final_response=latest_text,
                iterations_used=iterations,
                tool_calls_executed=total_tool_calls,
            )
        except Exception as exc:
            return AgentTurnResult(
                status="error",
                final_response=f"Execution error: {exc}",
                iterations_used=iterations,
                tool_calls_executed=total_tool_calls,
            )

    async def _stream_model_turn(
        self, ctx: AgentContext, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]
    ) -> tuple[str, List[ToolCallChunk]]:
        text_parts: List[str] = []
        tool_chunks: List[ToolCallChunk] = []

        stream = self.model_client.stream_chat(
            system_prompt=ctx.system_prompt,
            messages=messages,
            tools=tools,
        )

        async for chunk in stream:
            if chunk.thought and self.pipe_emitter:
                await self.pipe_emitter.emit_thought(ctx.turn_id, ctx.agent_type.value, chunk.thought)

            if chunk.text_delta:
                text_parts.append(chunk.text_delta)
                if self.pipe_emitter:
                    await self.pipe_emitter.emit_token(ctx.turn_id, ctx.agent_type.value, chunk.text_delta)

            if chunk.tool_calls:
                tool_chunks.extend(chunk.tool_calls)

        return "".join(text_parts), tool_chunks

    def _parse_tool_intents(self, tool_chunks: List[ToolCallChunk]) -> List[ToolCallIntent]:
        intents: List[ToolCallIntent] = []
        for chunk in tool_chunks:
            call_id = chunk.call_id or f"call_{uuid.uuid4().hex[:8]}"
            args: Dict[str, Any] = {}
            if chunk.arguments_json:
                try:
                    args = json.loads(chunk.arguments_json)
                except json.JSONDecodeError:
                    args = {"raw_arguments": chunk.arguments_json}

            intents.append(
                ToolCallIntent(
                    call_id=call_id,
                    tool_name=chunk.tool_name,
                    arguments=args,
                    thought_signature=chunk.thought_signature,
                )
            )
        return intents

    def _record_assistant_turn(
        self, messages: List[Dict[str, Any]], assistant_text: str, intents: List[ToolCallIntent]
    ) -> None:
        messages.append({
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": [i.to_dict() for i in intents],
        })

    async def _execute_and_record_tools(
        self, ctx: AgentContext, messages: List[Dict[str, Any]], intents: List[ToolCallIntent]
    ) -> None:
        local_intents = [i for i in intents if self._is_local_tool(i.tool_name)]
        remote_intents = [i for i in intents if not self._is_local_tool(i.tool_name)]

        for intent in local_intents:
            result_output = await self._execute_local_tool(intent)
            messages.append({
                "role": "tool",
                "tool_call_id": intent.call_id,
                "content": result_output,
            })

        if remote_intents:
            results = await self._execute_remote_tools(ctx, remote_intents)
            for res in results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": res.call_id,
                    "content": res.output,
                })

    def _is_local_tool(self, tool_name: str) -> bool:
        if self.memory_engine and self.memory_engine.is_memory_tool(tool_name):
            return True
        return tool_name.startswith("memory_")

    async def _execute_local_tool(self, intent: ToolCallIntent) -> str:
        if not self.memory_engine:
            return f"Error: memory engine unavailable for local tool {intent.tool_name}"
        try:
            return await self.memory_engine.execute_tool(intent.tool_name, intent.arguments)
        except Exception as exc:
            return f"Error executing local tool {intent.tool_name}: {exc}"

    async def _execute_remote_tools(
        self, ctx: AgentContext, remote_intents: List[ToolCallIntent]
    ) -> List[ToolCallResult]:
        if not self.pipe_emitter or not self.pipe_reader:
            return [
                ToolCallResult(
                    call_id=i.call_id,
                    output=f"Simulation result for remote tool {i.tool_name}",
                    is_error=False,
                )
                for i in remote_intents
            ]

        for intent in remote_intents:
            await self.pipe_emitter.emit_tool_call(ctx.turn_id, intent)

        return await self.pipe_reader.wait_for_tool_results(ctx.turn_id, len(remote_intents))


async def run_worker_agent(
    ctx: AgentContext,
    model_client: BaseLLMClient,
    memory_engine: Optional[MemoryEngineProtocol] = None,
    pipe_emitter: Optional[PipeEmitterProtocol] = None,
    pipe_reader: Optional[PipeReaderProtocol] = None,
) -> AgentTurnResult:
    """Convenience functional entrypoint to execute a worker agent turn."""
    engine = ReActEngine(
        model_client=model_client,
        memory_engine=memory_engine,
        pipe_emitter=pipe_emitter,
        pipe_reader=pipe_reader,
    )
    return await engine.run(ctx)

"""Framework-Free Async ReAct Engine for Layer 6 Agents."""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from src.agents.contracts import (
    AgentContext,
    AgentTurnResult,
    MemoryEngineProtocol,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ReActObserver,
    ToolCallIntent,
    ToolCallResult,
    ToolExecutionDomain,
    WorkerExecutionSnapshot,
)
from src.agents.engine.tool_dispatcher import ToolDispatcher
from src.models.base import BaseLLMClient
from src.models.types import ToolCallChunk

_active_workers: Dict[str, Dict[str, Any]] = {}
_global_observers: List[ReActObserver] = []


def register_global_react_observer(observer: ReActObserver) -> None:
    """Registers a process-wide observer for ReAct lifecycle events."""
    if observer not in _global_observers:
        _global_observers.append(observer)


def unregister_global_react_observer(observer: ReActObserver) -> None:
    """Unregisters a process-wide ReAct observer."""
    if observer in _global_observers:
        _global_observers.remove(observer)


def get_worker_snapshot(worker_id: str) -> WorkerExecutionSnapshot:
    """Returns the live execution snapshot for a specialist worker."""
    clean_id = worker_id.strip().lower()
    entry = _active_workers.get(clean_id)
    if not entry:
        return WorkerExecutionSnapshot(
            worker_id=clean_id,
            turn_id="",
            is_running=False,
            current_iteration=0,
            max_iterations=0,
            active_tool=None,
            elapsed_ms=0,
            total_tool_calls=0,
            tokens_streamed=0,
        )

    start_time = entry.get("start_time")
    elapsed_ms = int((time.perf_counter() - start_time) * 1000) if start_time else 0

    return WorkerExecutionSnapshot(
        worker_id=clean_id,
        turn_id=entry.get("turn_id", ""),
        is_running=entry.get("is_running", False),
        current_iteration=entry.get("current_iteration", 0),
        max_iterations=entry.get("max_iterations", 10),
        active_tool=entry.get("active_tool"),
        elapsed_ms=elapsed_ms,
        total_tool_calls=entry.get("total_tool_calls", 0),
        tokens_streamed=entry.get("tokens_streamed", 0),
    )


class ReActEngine:
    """Orchestrates an asynchronous ReAct loop with strict iteration guardrails."""

    def __init__(
        self,
        model_client: BaseLLMClient,
        memory_engine: Optional[MemoryEngineProtocol] = None,
        pipe_emitter: Optional[PipeEmitterProtocol] = None,
        pipe_reader: Optional[PipeReaderProtocol] = None,
        tool_dispatcher: Optional[ToolDispatcher] = None,
    ) -> None:
        self.model_client = model_client
        self.memory_engine = memory_engine
        self.pipe_emitter = pipe_emitter
        self.pipe_reader = pipe_reader
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher(
            pipe_emitter=pipe_emitter,
            pipe_reader=pipe_reader,
            memory_engine=memory_engine,
        )
        self._observers: List[ReActObserver] = []

    def register_react_observer(self, observer: ReActObserver) -> None:
        """Registers an observer for this engine instance."""
        if observer not in self._observers:
            self._observers.append(observer)

    def unregister_react_observer(self, observer: ReActObserver) -> None:
        """Unregisters an observer from this engine instance."""
        if observer in self._observers:
            self._observers.remove(observer)

    def _get_observers(self) -> List[ReActObserver]:
        return list(dict.fromkeys(self._observers + _global_observers))

    async def run(self, ctx: AgentContext) -> AgentTurnResult:
        """Executes the autonomous reasoning and action loop for a given context."""
        worker_id = (ctx.agent_type.value if hasattr(ctx.agent_type, "value") else str(ctx.agent_type)).lower()
        _active_workers[worker_id] = {
            "turn_id": ctx.turn_id,
            "is_running": True,
            "start_time": time.perf_counter(),
            "current_iteration": 0,
            "max_iterations": ctx.max_iterations,
            "active_tool": None,
            "total_tool_calls": 0,
            "tokens_streamed": 0,
        }

        messages = [dict(m) for m in ctx.conversation_history]
        messages.append({"role": "user", "content": ctx.user_prompt})

        tool_schemas = [t.to_dict() for t in ctx.available_tools] if ctx.available_tools else None
        iterations = 0
        total_tool_calls = 0
        latest_text = ""

        try:
            while iterations < ctx.max_iterations:
                iterations += 1
                if worker_id in _active_workers:
                    _active_workers[worker_id]["current_iteration"] = iterations

                # 2C: Sliding-window context guardrail to prevent context window overflow
                if len(messages) > 20:
                    messages = [messages[0]] + messages[-19:]

                step_text, tool_chunks = await self._stream_model_turn(ctx, messages, tool_schemas)
                if step_text:
                    latest_text = step_text

                if not tool_chunks:
                    for obs in self._get_observers():
                        try:
                            obs.on_iteration_end(worker_id, ctx.turn_id, iterations)
                        except Exception:
                            pass

                    return AgentTurnResult(
                        status="success",
                        final_response=latest_text,
                        iterations_used=iterations,
                        tool_calls_executed=total_tool_calls,
                    )

                tool_intents = self._parse_tool_intents(tool_chunks)
                total_tool_calls += len(tool_intents)

                self._record_assistant_turn(messages, step_text, tool_intents)
                challenge = await self._execute_and_record_tools(ctx, messages, tool_intents)

                # 2A: Human-in-the-Loop (HITL) Termination Guardrail
                if challenge:
                    return AgentTurnResult(
                        status="waiting_for_user_confirmation",
                        final_response=(
                            f"Action requires user confirmation: {challenge.get('command', 'destructive command')}\n"
                            f"Reason: {challenge.get('reason', 'Potentially destructive operation')}\n"
                            f"Please confirm to proceed."
                        ),
                        iterations_used=iterations,
                        tool_calls_executed=total_tool_calls,
                    )

                for obs in self._get_observers():
                    try:
                        obs.on_iteration_end(worker_id, ctx.turn_id, iterations)
                    except Exception:
                        pass

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
        finally:
            if worker_id in _active_workers:
                _active_workers[worker_id]["is_running"] = False

    async def _stream_model_turn(
        self, ctx: AgentContext, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]
    ) -> tuple[str, List[ToolCallChunk]]:
        text_parts: List[str] = []
        tool_chunks: List[ToolCallChunk] = []
        agent_name = ctx.agent_type.value if hasattr(ctx.agent_type, "value") else str(ctx.agent_type)
        worker_id = agent_name.lower()

        for attempt in range(3):
            text_parts.clear()
            tool_chunks.clear()
            try:
                stream = self.model_client.stream_chat(
                    system_prompt=ctx.system_prompt,
                    messages=messages,
                    tools=tools,
                )

                async for chunk in stream:
                    if chunk.thought:
                        if self.pipe_emitter:
                            await self.pipe_emitter.emit_thought(ctx.turn_id, agent_name, chunk.thought)
                        for obs in self._get_observers():
                            try:
                                obs.on_thought(worker_id, ctx.turn_id, chunk.thought)
                            except Exception:
                                pass

                    if chunk.text_delta:
                        text_parts.append(chunk.text_delta)
                        if worker_id in _active_workers:
                            _active_workers[worker_id]["tokens_streamed"] += max(1, len(chunk.text_delta) // 4)
                        if self.pipe_emitter:
                            await self.pipe_emitter.emit_token(ctx.turn_id, agent_name, chunk.text_delta)

                    if chunk.tool_calls:
                        tool_chunks.extend(chunk.tool_calls)

                return "".join(text_parts), tool_chunks
            except Exception as exc:
                err_msg = str(exc).lower()
                is_transient = (
                    "503" in err_msg
                    or "unavailable" in err_msg
                    or "high demand" in err_msg
                    or "429" in err_msg
                    or "quota" in err_msg
                    or "resource_exhausted" in err_msg
                    or "500" in err_msg
                    or "internal" in err_msg
                    or "502" in err_msg
                    or "504" in err_msg
                    or "bad gateway" in err_msg
                    or "gateway timeout" in err_msg
                )
                if is_transient and attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise

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
    ) -> Optional[Dict[str, Any]]:
        worker_id = (ctx.agent_type.value if hasattr(ctx.agent_type, "value") else str(ctx.agent_type)).lower()
        pending_challenge: Optional[Dict[str, Any]] = None

        for intent in intents:
            if worker_id in _active_workers:
                _active_workers[worker_id]["active_tool"] = intent.tool_name
                _active_workers[worker_id]["total_tool_calls"] += 1

            for obs in self._get_observers():
                try:
                    obs.on_tool_call(worker_id, ctx.turn_id, intent.tool_name, intent.arguments)
                except Exception:
                    pass

            is_local = self._is_local_tool(intent.tool_name, ctx)
            if is_local and hasattr(self.pipe_emitter, "emit_local_tool_call"):
                await self.pipe_emitter.emit_local_tool_call(ctx.turn_id, intent)

            start_time = time.perf_counter()
            tool_res = await self.tool_dispatcher.execute_intent(intent, ctx)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            if worker_id in _active_workers:
                _active_workers[worker_id]["active_tool"] = None

            for obs in self._get_observers():
                try:
                    obs.on_tool_result(worker_id, ctx.turn_id, intent.tool_name, tool_res.output, duration_ms)
                except Exception:
                    pass

            if is_local and hasattr(self.pipe_emitter, "emit_local_tool_result"):
                await self.pipe_emitter.emit_local_tool_result(
                    ctx.turn_id,
                    intent.tool_name,
                    tool_res.output,
                    duration_ms,
                    tool_res.is_error,
                )

            # 2A: Check for Human-in-the-Loop confirmation challenges
            sanitized_output = tool_res.output
            if "confirmation_required" in tool_res.output:
                try:
                    data = json.loads(tool_res.output)
                    if isinstance(data, dict) and data.get("status") == "confirmation_required":
                        pending_challenge = data
                        sanitized_data = {k: v for k, v in data.items() if k != "confirmation_id"}
                        sanitized_data["notice"] = "PAUSED: Potentially destructive action requires explicit user confirmation."
                        sanitized_output = json.dumps(sanitized_data, indent=2)
                except Exception:
                    pass

            # 2C: Truncate oversized tool output to avoid context overflow
            max_output_chars = 12000
            if len(sanitized_output) > max_output_chars:
                sanitized_output = (
                    sanitized_output[:max_output_chars]
                    + f"\n\n[Output truncated: exceeded {max_output_chars} characters limit. Use targeted file/data slicing to inspect specific portions.]"
                )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_res.call_id,
                "content": sanitized_output,
            })

            if pending_challenge:
                break

        return pending_challenge

    def _is_local_tool(self, tool_name: str, ctx: Optional[AgentContext] = None) -> bool:
        return self.tool_dispatcher.determine_domain(tool_name, ctx) == ToolExecutionDomain.PYTHON_LOCAL

    async def _execute_local_tool(self, intent: ToolCallIntent, ctx: Optional[AgentContext] = None) -> str:
        res = await self.tool_dispatcher.execute_intent(intent, ctx)
        return res.output

    async def _execute_remote_tools(
        self, ctx: AgentContext, remote_intents: List[ToolCallIntent]
    ) -> List[ToolCallResult]:
        return await self.tool_dispatcher.execute_intents(remote_intents, ctx)


async def run_worker_agent(
    ctx: AgentContext,
    model_client: BaseLLMClient,
    memory_engine: Optional[MemoryEngineProtocol] = None,
    pipe_emitter: Optional[PipeEmitterProtocol] = None,
    pipe_reader: Optional[PipeReaderProtocol] = None,
    tool_dispatcher: Optional[ToolDispatcher] = None,
) -> AgentTurnResult:
    """Convenience functional entrypoint to execute a worker agent turn."""
    engine = ReActEngine(
        model_client=model_client,
        memory_engine=memory_engine,
        pipe_emitter=pipe_emitter,
        pipe_reader=pipe_reader,
        tool_dispatcher=tool_dispatcher,
    )
    return await engine.run(ctx)

"""Python Resident Daemon bridge implementation for Layer 4."""

import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional

from src.agents.contracts import (
    AgentTurnResult,
    AgentType,
    PipeEmitterProtocol,
    PipeReaderProtocol,
    ToolCallIntent,
    ToolCallResult,
)
from src.bridge.daemon.transport import AsyncNDJSONTransport
from src.bridge.protocol.frames import (
    AgentThoughtPayload,
    AutonomousEventPayload,
    CancelTurnPayload,
    ErrorPayload,
    FrameType,
    MasterFrame,
    ReadyPayload,
    TokenPayload,
    TokenUsage,
    ToolCallPayload,
    ToolResultPayload,
    TurnCompletePayload,
    create_master_frame,
)


AgentRunner = Callable[
    [MasterFrame, PipeEmitterProtocol, PipeReaderProtocol],
    Coroutine[Any, Any, AgentTurnResult],
]


class PythonBridgeDaemon(PipeEmitterProtocol, PipeReaderProtocol):
    """Coordinates IPC frame routing, agent execution, and pipe streaming for Python."""

    def __init__(
        self,
        transport: AsyncNDJSONTransport,
        agent_runner: Optional[AgentRunner] = None,
    ) -> None:
        self.transport = transport
        self.agent_runner = agent_runner or self._default_agent_runner

        self._active_tasks: Dict[str, asyncio.Task[None]] = {}
        self._pending_tool_futures: Dict[str, asyncio.Future[ToolCallResult]] = {}
        self._turn_tool_call_ids: Dict[str, List[str]] = {}
        self._active_sessions: Dict[str, str] = {}
        self._is_running = False

    async def run(self) -> None:
        """Starts the transport loop, sends the ready handshake, and listens until EOF."""
        self._is_running = True
        await self._send_ready_frame()

        try:
            async for frame in self.transport.read_frames():
                await self._dispatch_frame(frame)
        finally:
            await self._shutdown()

    async def _send_ready_frame(self) -> None:
        """Emits ready handshake frame upon daemon startup."""
        ready_payload = ReadyPayload().to_dict()
        frame = create_master_frame(
            session_id="system",
            turn_id="handshake",
            frame_type=FrameType.READY,
            payload=ready_payload,
        )
        await self.transport.write_frame(frame)
        self.transport.log_diagnostic("Handshake ready frame emitted.")

    async def _dispatch_frame(self, frame: MasterFrame) -> None:
        """Routes an incoming frame from Go to the appropriate internal handler."""
        if frame.type == FrameType.START_TURN.value:
            await self._handle_start_turn(frame)
        elif frame.type == FrameType.TOOL_RESULT.value:
            self._handle_tool_result(frame)
        elif frame.type == FrameType.CANCEL_TURN.value:
            await self._handle_cancel_turn(frame)
        else:
            self.transport.log_diagnostic(f"Ignoring unhandled frame type: {frame.type}")

    async def _handle_start_turn(self, frame: MasterFrame) -> None:
        """Launches an asynchronous task to execute the requested agent reasoning turn."""
        turn_id = frame.turn_id
        session_id = frame.session_id
        self._active_sessions[turn_id] = session_id
        self._turn_tool_call_ids[turn_id] = []

        task = asyncio.create_task(
            self._execute_turn_lifecycle(frame),
            name=f"turn_{turn_id}",
        )
        self._active_tasks[turn_id] = task

    async def _execute_turn_lifecycle(self, frame: MasterFrame) -> None:
        """Executes the agent turn and transmits terminal turn_complete frame."""
        turn_id = frame.turn_id
        session_id = frame.session_id

        try:
            result = await self.agent_runner(frame, self, self)
            payload = TurnCompletePayload(
                status=result.status if result else "success",
                final_response=result.final_response if result else "",
                usage=TokenUsage(
                    prompt_tokens=result.prompt_tokens if result else 0,
                    completion_tokens=result.completion_tokens if result else 0,
                    total_tokens=(result.prompt_tokens + result.completion_tokens) if result else 0,
                ),
            ).to_dict()

            out_frame = create_master_frame(
                session_id=session_id,
                turn_id=turn_id,
                frame_type=FrameType.TURN_COMPLETE,
                payload=payload,
            )
            await self.transport.write_frame(out_frame)

        except asyncio.CancelledError:
            self.transport.log_diagnostic(f"Turn {turn_id} was cancelled.")
            payload = TurnCompletePayload(status="cancelled").to_dict()
            out_frame = create_master_frame(
                session_id=session_id,
                turn_id=turn_id,
                frame_type=FrameType.TURN_COMPLETE,
                payload=payload,
            )
            await self.transport.write_frame(out_frame)

        except Exception as exc:
            self.transport.log_diagnostic(f"Turn {turn_id} failed with error: {exc}")
            err_payload = ErrorPayload(code="TURN_ERROR", message=str(exc)).to_dict()
            err_frame = create_master_frame(
                session_id=session_id,
                turn_id=turn_id,
                frame_type=FrameType.ERROR,
                payload=err_payload,
            )
            await self.transport.write_frame(err_frame)

        finally:
            self._cleanup_turn(turn_id)

    async def _handle_cancel_turn(self, frame: MasterFrame) -> None:
        """Aborts an active in-flight turn."""
        turn_id = frame.turn_id
        task = self._active_tasks.get(turn_id)
        if task and not task.done():
            task.cancel()
            self.transport.log_diagnostic(f"Triggered cancellation for turn {turn_id}.")

    def _handle_tool_result(self, frame: MasterFrame) -> None:
        """Resolves the waiting Future for a returned tool execution result."""
        call_id = frame.payload.get("call_id", "")
        future = self._pending_tool_futures.get(call_id)
        if future and not future.done():
            is_error = frame.payload.get("is_error", frame.payload.get("exit_code", 0) != 0)
            res = ToolCallResult(
                call_id=call_id,
                output=str(frame.payload.get("output", "")),
                is_error=bool(is_error),
                artifact_path=frame.payload.get("artifact_path"),
            )
            future.set_result(res)
        else:
            self.transport.log_diagnostic(f"No pending future found for call_id: {call_id}")

    # PipeEmitterProtocol Implementation
    async def emit_thought(self, turn_id: str, agent_name: str, thought: str) -> None:
        session_id = self._active_sessions.get(turn_id, "default")
        payload = AgentThoughtPayload(thought=thought, agent_name=agent_name).to_dict()
        frame = create_master_frame(session_id, turn_id, FrameType.AGENT_THOUGHT, payload)
        await self.transport.write_frame(frame)

    async def emit_token(self, turn_id: str, agent_name: str, token: str) -> None:
        session_id = self._active_sessions.get(turn_id, "default")
        payload = TokenPayload(delta=token, agent_name=agent_name).to_dict()
        frame = create_master_frame(session_id, turn_id, FrameType.TOKEN, payload)
        await self.transport.write_frame(frame)

    async def emit_tool_call(self, turn_id: str, intent: ToolCallIntent) -> None:
        session_id = self._active_sessions.get(turn_id, "default")
        payload = ToolCallPayload(
            call_id=intent.call_id,
            tool_name=intent.tool_name,
            arguments=intent.arguments,
            idempotency_key=intent.idempotency_key,
        ).to_dict()

        if turn_id in self._turn_tool_call_ids:
            self._turn_tool_call_ids[turn_id].append(intent.call_id)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[ToolCallResult] = loop.create_future()
        self._pending_tool_futures[intent.call_id] = future

        frame = create_master_frame(session_id, turn_id, FrameType.TOOL_CALL, payload)
        await self.transport.write_frame(frame)

    async def emit_status(self, turn_id: str, agent_name: str, status_msg: str) -> None:
        await self.emit_thought(turn_id, agent_name, f"Status: {status_msg}")

    # PipeReaderProtocol Implementation
    async def wait_for_tool_results(self, turn_id: str, expected_count: int) -> List[ToolCallResult]:
        call_ids = self._turn_tool_call_ids.get(turn_id, [])
        target_ids = call_ids[-expected_count:] if expected_count <= len(call_ids) else call_ids

        futures = [self._pending_tool_futures[cid] for cid in target_ids if cid in self._pending_tool_futures]
        if not futures:
            return []

        results = await asyncio.gather(*futures)
        for cid in target_ids:
            self._pending_tool_futures.pop(cid, None)
        return list(results)

    async def emit_autonomous_event(
        self,
        source: str,
        event_type: str,
        summary: str,
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Sends an unsolicited proactive background event to Go."""
        payload = AutonomousEventPayload(
            source=source,
            event_type=event_type,
            summary=summary,
            raw_data=raw_data or {},
        ).to_dict()
        frame = create_master_frame("system", "autonomous", FrameType.AUTONOMOUS_EVENT, payload)
        await self.transport.write_frame(frame)

    def _cleanup_turn(self, turn_id: str) -> None:
        self._active_tasks.pop(turn_id, None)
        self._active_sessions.pop(turn_id, None)
        call_ids = self._turn_tool_call_ids.pop(turn_id, [])
        for cid in call_ids:
            self._pending_tool_futures.pop(cid, None)

    async def _shutdown(self) -> None:
        """Cancels remaining tasks and closes transport gracefully."""
        self._is_running = False
        for task in list(self._active_tasks.values()):
            if not task.done():
                task.cancel()
        await self.transport.close()

    async def _default_agent_runner(
        self,
        frame: MasterFrame,
        emitter: PipeEmitterProtocol,
        reader: PipeReaderProtocol,
    ) -> AgentTurnResult:
        """Dispatches turn to Layer 6 agent workers, Layer 2 Manager agent, or echo bench."""
        payload = frame.payload
        target_agent = payload.get("target_agent", "system")
        prompt = payload.get("prompt", "")
        history = payload.get("messages", [])

        if target_agent == "echo":
            await emitter.emit_thought(frame.turn_id, "echo", f"Processing echo prompt: {prompt}")

            final_output = f"Echo: {prompt}"
            if "call_tool:" in prompt:
                # Format: call_tool:<tool_name>:<args_json>
                parts = prompt.split("call_tool:", 1)[1].split(":", 1)
                tool_name = parts[0]
                import json
                tool_args = json.loads(parts[1]) if len(parts) > 1 else {}

                intent = ToolCallIntent(
                    call_id="call_echo_001",
                    tool_name=tool_name,
                    arguments=tool_args,
                )
                await emitter.emit_tool_call(frame.turn_id, intent)
                tool_results = await reader.wait_for_tool_results(frame.turn_id, expected_count=1)
                tool_res_str = tool_results[0].output if tool_results else "no result"
                final_output = f"Tool result: {tool_res_str}"

            await emitter.emit_token(frame.turn_id, "echo", final_output)
            return AgentTurnResult(
                status="success",
                final_response=final_output,
                prompt_tokens=len(prompt.split()),
                completion_tokens=len(final_output.split()),
            )

        if target_agent == "manager":
            from src.orchestrator.manager.manager import ManagerAgent
            mgr = ManagerAgent()
            plan = await mgr.plan(goal=prompt, conversation_history=history)
            import json
            plan_str = json.dumps(plan)
            return AgentTurnResult(status="success", final_response=plan_str)

        from src.agents.factory import create_agent
        agent_type = AgentType(target_agent) if target_agent in [e.value for e in AgentType] else AgentType.SYSTEM
        worker = create_agent(agent_type)
        return await worker.execute_turn(
            session_id=frame.session_id,
            turn_id=frame.turn_id,
            prompt=prompt,
            history=history,
            pipe_emitter=emitter,
            pipe_reader=reader,
        )

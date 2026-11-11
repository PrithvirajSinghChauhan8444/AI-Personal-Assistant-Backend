"""Unit tests for Layer 4 Python resident daemon and async bridge."""

import asyncio
from typing import List
import pytest

from src.agents.contracts import AgentTurnResult, ToolCallIntent, ToolCallResult
from src.bridge.daemon.bridge import PythonBridgeDaemon
from src.bridge.daemon.transport import AsyncNDJSONTransport
from src.bridge.protocol import (
    FrameType,
    MasterFrame,
    StartTurnPayload,
    ToolResultPayload,
    create_master_frame,
    decode_master_frame,
    encode_master_frame,
)


class MockTransport(AsyncNDJSONTransport):
    """In-memory mock transport for testing daemon dispatch and streaming without OS pipes."""

    def __init__(self) -> None:
        super().__init__()
        self.inbox: asyncio.Queue[MasterFrame] = asyncio.Queue()
        self.outbox: List[MasterFrame] = []
        self._closed_flag = False

    async def read_frames(self):
        while not self._closed_flag:
            try:
                frame = await asyncio.wait_for(self.inbox.get(), timeout=0.5)
                yield frame
            except asyncio.TimeoutError:
                break

    async def write_frame(self, frame: MasterFrame) -> None:
        self.outbox.append(frame)

    async def close(self) -> None:
        self._closed_flag = True


@pytest.mark.asyncio
async def test_daemon_handshake_ready() -> None:
    transport = MockTransport()
    daemon = PythonBridgeDaemon(transport=transport)

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    await transport.close()
    await task

    assert len(transport.outbox) >= 1
    ready_frame = transport.outbox[0]
    assert ready_frame.type == FrameType.READY.value
    assert ready_frame.payload["status"] == "ready"


@pytest.mark.asyncio
async def test_daemon_turn_lifecycle_and_streaming() -> None:
    transport = MockTransport()

    async def dummy_runner(frame, emitter, reader):
        await emitter.emit_thought(frame.turn_id, "system", "Starting step")
        await emitter.emit_token(frame.turn_id, "system", "Hello ")
        await emitter.emit_token(frame.turn_id, "system", "World!")
        return AgentTurnResult(
            status="success",
            final_response="Hello World!",
            prompt_tokens=10,
            completion_tokens=5,
        )

    daemon = PythonBridgeDaemon(transport=transport, agent_runner=dummy_runner)
    daemon_task = asyncio.create_task(daemon.run())

    # Feed start_turn frame into daemon inbox
    start_payload = StartTurnPayload(target_agent="system", prompt="greet").to_dict()
    start_frame = create_master_frame("sess_1", "turn_101", FrameType.START_TURN, start_payload)
    await transport.inbox.put(start_frame)

    # Let the turn execute
    await asyncio.sleep(0.1)
    await transport.close()
    await daemon_task

    types = [f.type for f in transport.outbox]
    assert FrameType.READY.value in types
    assert FrameType.AGENT_THOUGHT.value in types
    assert FrameType.TOKEN.value in types
    assert FrameType.TURN_COMPLETE.value in types

    tokens = [f.payload["delta"] for f in transport.outbox if f.type == FrameType.TOKEN.value]
    assert "".join(tokens) == "Hello World!"

    complete_frame = next(f for f in transport.outbox if f.type == FrameType.TURN_COMPLETE.value)
    assert complete_frame.payload["status"] == "success"
    assert complete_frame.payload["usage"]["total_tokens"] == 15


@pytest.mark.asyncio
async def test_daemon_tool_call_and_resolution() -> None:
    transport = MockTransport()

    async def tool_runner(frame, emitter, reader):
        intent = ToolCallIntent(
            call_id="call_99",
            tool_name="sys_exec",
            arguments={"command": "uname -a"},
        )
        await emitter.emit_tool_call(frame.turn_id, intent)
        results: List[ToolCallResult] = await reader.wait_for_tool_results(frame.turn_id, expected_count=1)
        output = results[0].output if results else "no_output"
        return AgentTurnResult(status="success", final_response=output)

    daemon = PythonBridgeDaemon(transport=transport, agent_runner=tool_runner)
    daemon_task = asyncio.create_task(daemon.run())

    # Send start_turn
    start_payload = StartTurnPayload(target_agent="system", prompt="run uname").to_dict()
    start_frame = create_master_frame("sess_1", "turn_102", FrameType.START_TURN, start_payload)
    await transport.inbox.put(start_frame)

    # Wait for tool call to be emitted
    await asyncio.sleep(0.05)
    tool_call_frame = next((f for f in transport.outbox if f.type == FrameType.TOOL_CALL.value), None)
    assert tool_call_frame is not None
    assert tool_call_frame.payload["call_id"] == "call_99"

    # Simulate Go returning tool_result
    res_payload = ToolResultPayload(
        call_id="call_99",
        exit_code=0,
        output="Linux 6.8.0-generic",
    ).to_dict()
    res_frame = create_master_frame("sess_1", "turn_102", FrameType.TOOL_RESULT, res_payload)
    await transport.inbox.put(res_frame)

    # Allow turn to complete
    await asyncio.sleep(0.05)
    await transport.close()
    await daemon_task

    complete = next(f for f in transport.outbox if f.type == FrameType.TURN_COMPLETE.value)
    assert complete.payload["status"] == "success"
    assert complete.payload["final_response"] == "Linux 6.8.0-generic"


@pytest.mark.asyncio
async def test_daemon_turn_cancellation() -> None:
    transport = MockTransport()

    async def hanging_runner(frame, emitter, reader):
        await asyncio.sleep(10.0)
        return AgentTurnResult(status="success", final_response="finished")

    daemon = PythonBridgeDaemon(transport=transport, agent_runner=hanging_runner)
    daemon_task = asyncio.create_task(daemon.run())

    start_payload = StartTurnPayload(target_agent="system", prompt="hang").to_dict()
    start_frame = create_master_frame("sess_1", "turn_cancel_test", FrameType.START_TURN, start_payload)
    await transport.inbox.put(start_frame)

    await asyncio.sleep(0.05)

    # Send cancel_turn
    cancel_frame = create_master_frame("sess_1", "turn_cancel_test", FrameType.CANCEL_TURN, {"reason": "user_cancelled"})
    await transport.inbox.put(cancel_frame)

    await asyncio.sleep(0.05)
    await transport.close()
    await daemon_task

    complete = next(f for f in transport.outbox if f.type == FrameType.TURN_COMPLETE.value)
    assert complete.payload["status"] == "cancelled"


@pytest.mark.asyncio
async def test_daemon_runner_exception_emits_error_frame() -> None:
    transport = MockTransport()

    async def failing_runner(frame, emitter, reader):
        raise ValueError("Simulated runner crash")

    daemon = PythonBridgeDaemon(transport=transport, agent_runner=failing_runner)
    daemon_task = asyncio.create_task(daemon.run())

    start_payload = StartTurnPayload(target_agent="system", prompt="fail").to_dict()
    start_frame = create_master_frame("sess_1", "turn_fail_test", FrameType.START_TURN, start_payload)
    await transport.inbox.put(start_frame)

    await asyncio.sleep(0.05)
    await transport.close()
    await daemon_task

    err_frame = next((f for f in transport.outbox if f.type == FrameType.ERROR.value), None)
    assert err_frame is not None
    assert err_frame.payload["code"] == "TURN_ERROR"
    assert "Simulated runner crash" in err_frame.payload["message"]


@pytest.mark.asyncio
async def test_daemon_autonomous_event_emission() -> None:
    transport = MockTransport()
    daemon = PythonBridgeDaemon(transport=transport)

    await daemon.emit_autonomous_event(
        source="cron_watcher",
        event_type="file_change",
        summary="Modified config/settings.json",
        raw_data={"file": "config/settings.json"},
    )

    assert len(transport.outbox) == 1
    evt = transport.outbox[0]
    assert evt.type == FrameType.AUTONOMOUS_EVENT.value
    assert evt.payload["source"] == "cron_watcher"
    assert evt.payload["event_type"] == "file_change"
    assert evt.payload["summary"] == "Modified config/settings.json"


@pytest.mark.asyncio
async def test_daemon_default_runner_echo_mode() -> None:
    transport = MockTransport()
    daemon = PythonBridgeDaemon(transport=transport)
    daemon_task = asyncio.create_task(daemon.run())

    start_payload = StartTurnPayload(target_agent="echo", prompt="live_pipe_message").to_dict()
    start_frame = create_master_frame("sess_echo", "turn_echo_1", FrameType.START_TURN, start_payload)
    await transport.inbox.put(start_frame)

    await asyncio.sleep(0.05)
    await transport.close()
    await daemon_task

    tokens = [f.payload["delta"] for f in transport.outbox if f.type == FrameType.TOKEN.value]
    assert any("live_pipe_message" in tok for tok in tokens)

    complete = next(f for f in transport.outbox if f.type == FrameType.TURN_COMPLETE.value)
    assert complete.payload["status"] == "success"
    assert "live_pipe_message" in complete.payload["final_response"]


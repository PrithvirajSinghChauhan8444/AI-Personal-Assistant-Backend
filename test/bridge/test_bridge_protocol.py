"""Unit tests for Layer 4 wire protocol and NDJSON framing in Python."""

import pytest

from src.bridge.protocol import (
    AgentThoughtPayload,
    AutonomousEventPayload,
    CancelTurnPayload,
    ErrorPayload,
    FrameType,
    MasterFrame,
    ReadyPayload,
    StartTurnPayload,
    TokenPayload,
    TokenUsage,
    ToolCallPayload,
    ToolResultPayload,
    TurnCompletePayload,
    create_master_frame,
    decode_master_frame,
    encode_master_frame,
)


def test_master_frame_validation() -> None:
    frame = create_master_frame(
        session_id="sess_abc",
        turn_id="turn_123",
        frame_type=FrameType.START_TURN,
        payload={"prompt": "test prompt"},
    )
    assert frame.session_id == "sess_abc"
    assert frame.turn_id == "turn_123"
    assert frame.type == "start_turn"
    assert frame.payload["prompt"] == "test prompt"


def test_master_frame_empty_validation_errors() -> None:
    with pytest.raises(ValueError, match="frame_id cannot be empty"):
        MasterFrame(
            frame_id="",
            session_id="s",
            turn_id="t",
            timestamp_ms=0,
            type="ready",
            payload={},
        ).validate()

    with pytest.raises(ValueError, match="turn_id cannot be empty for non-ready frames"):
        MasterFrame(
            frame_id="f1",
            session_id="s",
            turn_id="",
            timestamp_ms=0,
            type="start_turn",
            payload={},
        ).validate()


def test_codec_roundtrip() -> None:
    original = create_master_frame(
        session_id="sess_xyz",
        turn_id="turn_999",
        frame_type=FrameType.AGENT_THOUGHT,
        payload=AgentThoughtPayload(thought="Deciding on next step", agent_name="system").to_dict(),
    )

    encoded = encode_master_frame(original)
    assert encoded.endswith("\n")

    decoded = decode_master_frame(encoded)
    assert decoded.frame_id == original.frame_id
    assert decoded.session_id == original.session_id
    assert decoded.turn_id == original.turn_id
    assert decoded.type == FrameType.AGENT_THOUGHT.value
    assert decoded.payload["thought"] == "Deciding on next step"
    assert decoded.payload["agent_name"] == "system"


def test_decode_invalid_line() -> None:
    with pytest.raises(ValueError, match="Cannot decode empty line"):
        decode_master_frame("   \n")

    with pytest.raises(Exception):
        decode_master_frame("not valid json\n")


def test_payload_dataclasses() -> None:
    ready = ReadyPayload(status="ready", version="2.0.0").to_dict()
    assert ready["status"] == "ready"
    assert ready["version"] == "2.0.0"

    tool_call = ToolCallPayload(
        call_id="c_1",
        tool_name="sys_exec",
        arguments={"command": "ls -la"},
        idempotency_key="k_1",
    ).to_dict()
    assert tool_call["call_id"] == "c_1"
    assert tool_call["tool_name"] == "sys_exec"

    tool_res = ToolResultPayload(call_id="c_1", exit_code=0, output="file.txt").to_dict()
    assert tool_res["output"] == "file.txt"
    assert tool_res["exit_code"] == 0

    complete = TurnCompletePayload(
        status="success",
        final_response="Done",
        usage=TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
    ).to_dict()
    assert complete["status"] == "success"
    assert complete["usage"]["total_tokens"] == 120

    event = AutonomousEventPayload(
        source="gmail_daemon",
        event_type="new_email",
        summary="Important alert",
    ).to_dict()
    assert event["source"] == "gmail_daemon"

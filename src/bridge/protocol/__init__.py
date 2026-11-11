"""Wire protocol definitions and framing codecs for Layer 4 IPC Bridge."""

from src.bridge.protocol.frames import (
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

__all__ = [
    "FrameType",
    "MasterFrame",
    "ReadyPayload",
    "StartTurnPayload",
    "AgentThoughtPayload",
    "ToolCallPayload",
    "ToolResultPayload",
    "TokenPayload",
    "TokenUsage",
    "TurnCompletePayload",
    "AutonomousEventPayload",
    "CancelTurnPayload",
    "ErrorPayload",
    "create_master_frame",
    "encode_master_frame",
    "decode_master_frame",
]

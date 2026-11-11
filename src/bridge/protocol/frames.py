"""Data contracts and NDJSON serialization codecs for Layer 4 IPC Bridge."""

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import time
from typing import Any, Dict, List, Optional
import uuid


class FrameType(str, Enum):
    """Wire protocol discriminators."""
    READY = "ready"
    START_TURN = "start_turn"
    TOOL_RESULT = "tool_result"
    CANCEL_TURN = "cancel_turn"
    AGENT_THOUGHT = "agent_thought"
    TOOL_CALL = "tool_call"
    TOKEN = "token"
    TURN_COMPLETE = "turn_complete"
    AUTONOMOUS_EVENT = "autonomous_event"
    ERROR = "error"


@dataclass
class MasterFrame:
    """Standard wire envelope for cross-runtime IPC communication."""
    frame_id: str
    session_id: str
    turn_id: str
    timestamp_ms: int
    type: str
    payload: Dict[str, Any]

    def validate(self) -> None:
        """Enforces frame invariants."""
        if not self.frame_id:
            raise ValueError("frame_id cannot be empty")
        if not self.type:
            raise ValueError("frame type cannot be empty")
        if not self.turn_id and self.type != FrameType.READY.value:
            raise ValueError("turn_id cannot be empty for non-ready frames")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dictionary")


@dataclass
class ReadyPayload:
    status: str = "ready"
    version: str = "1.0.0"
    supported_agents: List[str] = field(default_factory=lambda: ["system", "browser", "research", "productivity", "manager"])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChatMessage:
    role: str
    content: str
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {"role": self.role, "content": self.content}
        if self.name:
            data["name"] = self.name
        return data


@dataclass
class StartTurnPayload:
    target_agent: str
    prompt: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    tools: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentThoughtPayload:
    thought: str
    agent_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {"thought": self.thought}
        if self.agent_name:
            data["agent_name"] = self.agent_name
        return data


@dataclass
class ToolCallPayload:
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    idempotency_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
        }
        if self.idempotency_key:
            data["idempotency_key"] = self.idempotency_key
        return data


@dataclass
class ToolResultPayload:
    call_id: str
    exit_code: int
    output: str
    artifact_path: Optional[str] = None
    duration_ms: int = 0
    is_error: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TokenPayload:
    delta: str
    agent_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {"delta": self.delta}
        if self.agent_name:
            data["agent_name"] = self.agent_name
        return data


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TurnCompletePayload:
    status: str
    final_response: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "status": self.status,
            "final_response": self.final_response,
            "usage": self.usage.to_dict(),
        }
        return data


@dataclass
class AutonomousEventPayload:
    source: str
    event_type: str
    summary: str
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CancelTurnPayload:
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorPayload:
    code: str
    message: str
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {"code": self.code, "message": self.message}
        if self.details:
            data["details"] = self.details
        return data


def create_master_frame(
    session_id: str,
    turn_id: str,
    frame_type: FrameType | str,
    payload: Dict[str, Any],
) -> MasterFrame:
    """Builds and validates a MasterFrame envelope."""
    type_val = frame_type.value if isinstance(frame_type, FrameType) else str(frame_type)
    frame = MasterFrame(
        frame_id=f"frm_{uuid.uuid4()}",
        session_id=session_id,
        turn_id=turn_id,
        timestamp_ms=int(time.time() * 1000),
        type=type_val,
        payload=payload,
    )
    frame.validate()
    return frame


def encode_master_frame(frame: MasterFrame) -> str:
    """Encodes a MasterFrame into a single line NDJSON string with newline."""
    frame.validate()
    serialized = json.dumps(asdict(frame), separators=(",", ":"))
    return f"{serialized}\n"


def decode_master_frame(line: str) -> MasterFrame:
    """Decodes an NDJSON line into a validated MasterFrame."""
    stripped = line.strip()
    if not stripped:
        raise ValueError("Cannot decode empty line")

    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("Decoded NDJSON must be a JSON object")

    frame = MasterFrame(
        frame_id=data.get("frame_id", ""),
        session_id=data.get("session_id", ""),
        turn_id=data.get("turn_id", ""),
        timestamp_ms=data.get("timestamp_ms", 0),
        type=data.get("type", ""),
        payload=data.get("payload", {}),
    )
    frame.validate()
    return frame

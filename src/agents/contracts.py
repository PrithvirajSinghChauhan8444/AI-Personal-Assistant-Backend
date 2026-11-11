"""Core contracts, data structures, and protocols for Layer 6 Agent Engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class AgentType(str, Enum):
    """Supported agent personas."""
    MANAGER = "manager"
    SYSTEM = "system"
    RESEARCH = "research"
    BROWSER = "browser"
    PRODUCTIVITY = "productivity"


@dataclass
class ToolDefinition:
    """Cognitive specification of a tool exposed to the language model."""
    name: str
    description: str
    parameters: Dict[str, Any]
    prompt_usage_tip: str = ""
    category: str = "general"
    risk: str = "LOW"

    def to_dict(self) -> Dict[str, Any]:
        """Converts into standard function-calling tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCallIntent:
    """Represents an agent's intent to invoke a specific tool."""
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    idempotency_key: str = ""
    thought_signature: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.call_id,
            "type": "function",
            "function": {
                "name": self.tool_name,
                "arguments": self.arguments,
            },
        }
        if self.thought_signature:
            data["thought_signature"] = self.thought_signature
        return data


@dataclass
class ToolCallResult:
    """Standardized result returned after tool execution."""
    call_id: str
    output: str
    is_error: bool = False
    artifact_path: Optional[str] = None


@dataclass
class AgentContext:
    """Execution context and constraints for an autonomous agent turn."""
    session_id: str
    turn_id: str
    agent_type: AgentType
    user_prompt: str
    system_prompt: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    available_tools: List[ToolDefinition] = field(default_factory=list)
    max_iterations: int = 10
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTurnResult:
    """Terminal outcome of an agent turn."""
    status: str
    final_response: str
    iterations_used: int = 0
    tool_calls_executed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    subtask_results: List[Dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class PipeEmitterProtocol(Protocol):
    """Interface for streaming events to the Layer 4 Bridge."""

    async def emit_thought(self, turn_id: str, agent_name: str, thought: str) -> None:
        ...

    async def emit_token(self, turn_id: str, agent_name: str, token: str) -> None:
        ...

    async def emit_tool_call(self, turn_id: str, intent: ToolCallIntent) -> None:
        ...

    async def emit_status(self, turn_id: str, agent_name: str, status_msg: str) -> None:
        ...


@runtime_checkable
class PipeReaderProtocol(Protocol):
    """Interface for awaiting tool execution results from Layer 4 / Go."""

    async def wait_for_tool_results(self, turn_id: str, expected_count: int) -> List[ToolCallResult]:
        ...


@runtime_checkable
class MemoryEngineProtocol(Protocol):
    """Interface for zero-latency local memory tools (Layer 5)."""

    def is_memory_tool(self, tool_name: str) -> bool:
        ...

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        ...

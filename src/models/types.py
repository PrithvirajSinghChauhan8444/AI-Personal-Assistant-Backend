"""Normalized data structures and exceptions for Layer 7 Model Engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelProvider(str, Enum):
    """Supported LLM providers."""
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


@dataclass(frozen=True)
class ToolCallChunk:
    """Represents a tool invocation emitted by the model during a turn."""
    call_id: str
    tool_name: str
    arguments_json: str
    thought_signature: Optional[bytes] = None


@dataclass
class StreamChunk:
    """Normalized chunk yielded by all LLM streaming clients."""
    text_delta: Optional[str] = None
    thought: Optional[str] = None
    tool_calls: Optional[List[ToolCallChunk]] = None
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


@dataclass
class ChatMessage:
    """Represents a single message in the conversation history."""
    role: str
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


class ModelEngineError(Exception):
    """Base exception for all model engine failures."""
    pass


class AuthenticationError(ModelEngineError):
    """Raised when provider credentials or API keys are missing or invalid."""
    pass


class QuotaExceededError(ModelEngineError):
    """Raised when provider rate limits or token quotas are exhausted."""
    pass


class ModelNotFoundError(ModelEngineError):
    """Raised when the specified model ID is not supported or recognized."""
    pass


class ProviderConnectionError(ModelEngineError):
    """Raised when network communication with the LLM provider fails."""
    pass

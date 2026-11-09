"""Base abstract interface for all LLM providers in Layer 7 Model Engine."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

from .types import StreamChunk


class BaseLLMClient(ABC):
    """Abstract parent class establishing the unified contract for all LLM providers."""

    def __init__(self, model_name: str, temperature: float = 0.0, timeout_seconds: float = 60.0, **kwargs: Any) -> None:
        self.model_name = model_name
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.extra_kwargs = kwargs

    @abstractmethod
    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streams normalized chunks from the underlying LLM provider.

        Yields:
            StreamChunk: Normalized chunk containing text deltas, thoughts, or tool calls.
        """
        pass

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Convenience method for non-streaming single-turn text generation."""
        messages = [{"role": "user", "content": user_prompt}]
        text_parts: List[str] = []
        async for chunk in self.stream_chat(system_prompt, messages, tools):
            if chunk.text_delta:
                text_parts.append(chunk.text_delta)
        return "".join(text_parts)

    def normalize_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Any:
        """Converts generic JSON schemas into provider-specific tool representations."""
        return tools

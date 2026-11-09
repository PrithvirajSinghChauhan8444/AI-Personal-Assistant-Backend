"""OpenAI LLM provider using official AsyncOpenAI SDK with streaming."""

import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from ..base import BaseLLMClient
from ..types import (
    AuthenticationError,
    ProviderConnectionError,
    QuotaExceededError,
    StreamChunk,
    ToolCallChunk,
)


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI models (GPT-4o, o-series) using AsyncOpenAI."""

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise AuthenticationError("OPENAI_API_KEY is not configured in environment or client.")

        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=base_url)

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streams text deltas, tool call chunks, and token usage from OpenAI."""
        payload_messages = self._build_messages(system_prompt, messages)
        stream_kwargs = self._build_kwargs(payload_messages, tools)

        try:
            stream = await self._client.chat.completions.create(**stream_kwargs)
            async for chunk in stream:
                if chunk.usage:
                    yield StreamChunk(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                    )

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if getattr(delta, "content", None):
                    yield StreamChunk(text_delta=delta.content)

                if getattr(delta, "tool_calls", None):
                    for tc in delta.tool_calls:
                        fn = tc.function
                        if fn and fn.name:
                            call_id = tc.id or f"call_{uuid4().hex[:12]}"
                            yield StreamChunk(
                                tool_calls=[
                                    ToolCallChunk(
                                        call_id=call_id,
                                        tool_name=fn.name,
                                        arguments_json=fn.arguments or "{}",
                                    )
                                ]
                            )

                if choice.finish_reason:
                    yield StreamChunk(finish_reason=choice.finish_reason)

        except Exception as exc:
            self._handle_exception(exc)

    def _build_messages(self, system_prompt: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepend system prompt if provided."""
        result: List[Dict[str, Any]] = []
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})
        for msg in messages:
            result.append({"role": msg.get("role", "user"), "content": str(msg.get("content", ""))})
        return result

    def _build_kwargs(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Assembles arguments for create() call."""
        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        # Temperature is omitted or kept at 1 for o-series reasoning models
        if not self.model_name.startswith("o"):
            kwargs["temperature"] = self.temperature

        if tools:
            kwargs["tools"] = tools

        return kwargs

    def _handle_exception(self, exc: Exception) -> None:
        """Translates OpenAI exceptions to typed errors."""
        err_msg = str(exc).lower()
        if "rate_limit" in err_msg or "429" in err_msg or "insufficient_quota" in err_msg:
            raise QuotaExceededError(f"OpenAI quota/rate limit error: {exc}") from exc
        if "invalid_api_key" in err_msg or "401" in err_msg or "authentication" in err_msg:
            raise AuthenticationError(f"OpenAI authentication failed: {exc}") from exc
        raise ProviderConnectionError(f"OpenAI stream failure: {exc}") from exc

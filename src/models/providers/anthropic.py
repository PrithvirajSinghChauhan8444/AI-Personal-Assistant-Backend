"""Anthropic Claude LLM provider using direct async HTTP SSE streaming."""

import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

import httpx

from ..base import BaseLLMClient
from ..types import (
    AuthenticationError,
    ProviderConnectionError,
    QuotaExceededError,
    StreamChunk,
    ToolCallChunk,
)


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models with streaming and thinking support."""

    API_URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        model_name: str = "claude-3-7-sonnet-20250219",
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise AuthenticationError("ANTHROPIC_API_KEY is not configured in environment or client.")
        self.max_tokens = max_tokens

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streams text deltas, thinking blocks, and tool use blocks from Anthropic."""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.DEFAULT_ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        payload = self._build_payload(system_prompt, messages, tools)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", self.API_URL, headers=headers, json=payload) as response:
                    if response.status_code == 401 or response.status_code == 403:
                        err_text = await response.aread()
                        raise AuthenticationError(f"Anthropic authentication failed: {err_text.decode('utf-8', 'ignore')}")
                    if response.status_code == 429:
                        err_text = await response.aread()
                        raise QuotaExceededError(f"Anthropic rate limit/quota error: {err_text.decode('utf-8', 'ignore')}")
                    if response.status_code != 200:
                        err_text = await response.aread()
                        raise ProviderConnectionError(f"Anthropic API error (status {response.status_code}): {err_text.decode('utf-8', 'ignore')}")

                    async for chunk in self._parse_sse_stream(response):
                        yield chunk

        except (AuthenticationError, QuotaExceededError, ProviderConnectionError):
            raise
        except Exception as exc:
            raise ProviderConnectionError(f"Anthropic connection failure: {exc}") from exc

    def _build_payload(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Formats request body for Anthropic Messages API."""
        formatted_messages = [
            {"role": msg.get("role", "user"), "content": str(msg.get("content", ""))}
            for msg in messages
            if msg.get("role") != "system"
        ]

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "messages": formatted_messages,
            "temperature": self.temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            payload["tools"] = tools

        return payload

    async def _parse_sse_stream(self, response: httpx.Response) -> AsyncIterator[StreamChunk]:
        """Parses Server-Sent Events stream from Anthropic."""
        active_tool_id: Optional[str] = None
        active_tool_name: Optional[str] = None
        active_tool_input_json: str = ""

        async for line in response.aiter_lines():
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue

            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break

            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")

            if event_type == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    active_tool_id = block.get("id", f"call_{uuid4().hex[:12]}")
                    active_tool_name = block.get("name", "")
                    active_tool_input_json = ""

            elif event_type == "content_block_delta":
                delta = event.get("delta", {})
                delta_type = delta.get("type")

                # Handle Claude internal reasoning / thinking deltas
                if delta_type == "thinking_delta":
                    yield StreamChunk(thought=delta.get("thinking", ""))
                elif delta_type == "text_delta":
                    yield StreamChunk(text_delta=delta.get("text", ""))
                elif delta_type == "input_json_delta":
                    active_tool_input_json += delta.get("partial_json", "")

            elif event_type == "content_block_stop":
                if active_tool_name:
                    yield StreamChunk(
                        tool_calls=[
                            ToolCallChunk(
                                call_id=active_tool_id or f"call_{uuid4().hex[:12]}",
                                tool_name=active_tool_name,
                                arguments_json=active_tool_input_json or "{}",
                            )
                        ]
                    )
                    active_tool_id = None
                    active_tool_name = None
                    active_tool_input_json = ""

            elif event_type == "message_start":
                msg = event.get("message", {})
                usage = msg.get("usage", {})
                if usage:
                    yield StreamChunk(prompt_tokens=usage.get("input_tokens", 0))

            elif event_type == "message_delta":
                usage = event.get("usage", {})
                if usage:
                    yield StreamChunk(completion_tokens=usage.get("output_tokens", 0))
                stop_reason = event.get("delta", {}).get("stop_reason")
                if stop_reason:
                    yield StreamChunk(finish_reason=stop_reason)

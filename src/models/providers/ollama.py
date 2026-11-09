"""Local Ollama LLM provider using direct async HTTP NDJSON streaming."""

import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

import httpx

from ..base import BaseLLMClient
from ..types import (
    ModelNotFoundError,
    ProviderConnectionError,
    StreamChunk,
    ToolCallChunk,
)


class OllamaClient(BaseLLMClient):
    """Client for local Ollama instances (e.g. llama3.2, qwen2.5-coder, gemma4) via NDJSON."""

    DEFAULT_HOST = "http://localhost:11434"

    def __init__(
        self,
        model_name: str = "llama3.2",
        temperature: float = 0.0,
        host: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)
        self.host = (host or os.environ.get("OLLAMA_HOST") or self.DEFAULT_HOST).rstrip("/")

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streams text deltas and tool calls from local Ollama endpoint."""
        url = f"{self.host}/api/chat"
        payload = self._build_payload(system_prompt, messages, tools)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code == 404:
                        err_text = await response.aread()
                        raise ModelNotFoundError(f"Ollama model '{self.model_name}' not found: {err_text.decode('utf-8', 'ignore')}")
                    if response.status_code != 200:
                        err_text = await response.aread()
                        raise ProviderConnectionError(f"Ollama returned error status {response.status_code}: {err_text.decode('utf-8', 'ignore')}")

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        message = item.get("message", {})
                        content = message.get("content", "")
                        if content:
                            yield StreamChunk(text_delta=content)

                        tool_calls = message.get("tool_calls", [])
                        if tool_calls:
                            extracted = []
                            for tc in tool_calls:
                                fn = tc.get("function", {})
                                tool_name = fn.get("name", "")
                                args = fn.get("arguments", {})
                                args_json = json.dumps(args) if isinstance(args, dict) else str(args)
                                extracted.append(
                                    ToolCallChunk(
                                        call_id=f"call_{uuid4().hex[:12]}",
                                        tool_name=tool_name,
                                        arguments_json=args_json,
                                    )
                                )
                            yield StreamChunk(tool_calls=extracted)

                        if item.get("done", False):
                            prompt_tokens = item.get("prompt_eval_count")
                            eval_tokens = item.get("eval_count")
                            yield StreamChunk(
                                finish_reason="stop",
                                prompt_tokens=prompt_tokens,
                                completion_tokens=eval_tokens,
                            )

        except (ModelNotFoundError, ProviderConnectionError):
            raise
        except Exception as exc:
            raise ProviderConnectionError(f"Failed to connect to Ollama at {self.host}: {exc}") from exc

    def _build_payload(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Constructs request payload for /api/chat."""
        formatted_messages: List[Dict[str, Any]] = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            formatted_messages.append({
                "role": msg.get("role", "user"),
                "content": str(msg.get("content", "")),
            })

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "stream": True,
            "options": {
                "temperature": self.temperature,
            },
        }

        if tools:
            payload["tools"] = tools

        return payload

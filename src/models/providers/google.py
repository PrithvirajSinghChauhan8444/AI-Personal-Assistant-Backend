"""Google Gemini LLM provider using modern google-genai SDK with streaming and thoughts."""

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


class GoogleClient(BaseLLMClient):
    """Client for Google Gemini models via google-genai SDK."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise AuthenticationError("GEMINI_API_KEY is not configured in environment or client.")

        from google import genai
        self._client = genai.Client(api_key=self.api_key)

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streams text deltas, thoughts, and tool call invocations from Gemini."""
        from google.genai import types

        formatted_contents = self._format_messages(messages)
        config = self._build_config(types, system_prompt, tools)

        try:
            response_stream = await self._client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=formatted_contents,
                config=config,
            )

            async for chunk in response_stream:
                for candidate in getattr(chunk, "candidates", []) or []:
                    content = getattr(candidate, "content", None)
                    if not content or not getattr(content, "parts", None):
                        continue

                    for part in content.parts:
                        # Extract reasoning thought delta if present
                        if getattr(part, "thought", False) and getattr(part, "text", None):
                            yield StreamChunk(thought=part.text)
                        elif getattr(part, "text", None):
                            yield StreamChunk(text_delta=part.text)

                        # Extract function/tool call intents
                        function_call = getattr(part, "function_call", None)
                        if function_call:
                            call_id = f"call_{uuid4().hex[:12]}"
                            tool_name = getattr(function_call, "name", "")
                            args_dict = dict(getattr(function_call, "args", {}) or {})
                            yield StreamChunk(
                                tool_calls=[
                                    ToolCallChunk(
                                        call_id=call_id,
                                        tool_name=tool_name,
                                        arguments_json=json.dumps(args_dict),
                                    )
                                ]
                            )

                # Track token usage if reported in chunk metadata
                usage = getattr(chunk, "usage_metadata", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_token_count", None)
                    completion_tokens = getattr(usage, "candidates_token_count", None)
                    if prompt_tokens or completion_tokens:
                        yield StreamChunk(
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                        )

        except Exception as exc:
            self._handle_exception(exc)

    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Converts generic chat history into Gemini contents format."""
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            mapped_role = "model" if role in ("assistant", "model") else "user"
            contents.append({"role": mapped_role, "parts": [{"text": str(content)}]})
        return contents

    def _build_config(self, types_module: Any, system_prompt: str, tools: Optional[List[Dict[str, Any]]]) -> Any:
        """Constructs GenerateContentConfig with temperature and optional system instruction."""
        config_kwargs: Dict[str, Any] = {
            "temperature": self.temperature,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        if tools:
            config_kwargs["tools"] = tools

        return types_module.GenerateContentConfig(**config_kwargs)

    def _handle_exception(self, exc: Exception) -> None:
        """Categorizes and re-raises provider-specific errors into standard typed exceptions."""
        err_msg = str(exc).lower()
        if "429" in err_msg or "quota" in err_msg or "resource_exhausted" in err_msg:
            raise QuotaExceededError(f"Gemini quota exceeded: {exc}") from exc
        if "401" in err_msg or "403" in err_msg or "api_key" in err_msg or "permission" in err_msg:
            raise AuthenticationError(f"Gemini authentication failed: {exc}") from exc
        raise ProviderConnectionError(f"Gemini streaming error: {exc}") from exc

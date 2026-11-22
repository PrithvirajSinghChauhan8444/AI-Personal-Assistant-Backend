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
        fallback_models: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise AuthenticationError("GEMINI_API_KEY is not configured in environment or client.")

        from google import genai
        self._client = genai.Client(api_key=self.api_key)

        if fallback_models is None:
            fallbacks: List[str] = []
            try:
                from src.agents.factory import load_system_config
                sys_cfg = load_system_config()
                raw_fallbacks = sys_cfg.get("models", {}).get("fallback_models", [])
                for fb in raw_fallbacks:
                    fb_clean = fb.split(":")[-1].strip()
                    if fb_clean and fb_clean not in fallbacks:
                        fallbacks.append(fb_clean)
            except Exception:
                pass
            if not fallbacks:
                fallbacks = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"]
            fallback_models = fallbacks
        self.fallback_models = fallback_models

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streams text deltas, thoughts, and tool call invocations from Gemini with automatic quota fallback."""
        from google.genai import types

        formatted_contents = self._format_messages(types, messages)
        config = self._build_config(types, system_prompt, tools)

        models_to_try = [self.model_name]
        for fb in self.fallback_models:
            if fb != self.model_name and fb not in models_to_try:
                models_to_try.append(fb)

        for attempt_idx, candidate_model in enumerate(models_to_try):
            streamed_any_chunks = False
            try:
                response_stream = await self._client.aio.models.generate_content_stream(
                    model=candidate_model,
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
                                streamed_any_chunks = True
                                yield StreamChunk(thought=part.text)
                            elif getattr(part, "text", None):
                                streamed_any_chunks = True
                                yield StreamChunk(text_delta=part.text)

                            # Extract function/tool call intents
                            function_call = getattr(part, "function_call", None)
                            if function_call:
                                streamed_any_chunks = True
                                call_id = getattr(function_call, "id", None) or f"call_{uuid4().hex[:12]}"
                                tool_name = getattr(function_call, "name", "")
                                args_dict = dict(getattr(function_call, "args", {}) or {})
                                thought_sig = getattr(part, "thought_signature", None)
                                yield StreamChunk(
                                    tool_calls=[
                                        ToolCallChunk(
                                            call_id=call_id,
                                            tool_name=tool_name,
                                            arguments_json=json.dumps(args_dict),
                                            thought_signature=thought_sig,
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

                # Successful stream completion
                return

            except Exception as exc:
                err_msg = str(exc).lower()
                is_recoverable = (
                    "429" in err_msg
                    or "quota" in err_msg
                    or "resource_exhausted" in err_msg
                    or "503" in err_msg
                    or "unavailable" in err_msg
                    or "high demand" in err_msg
                    or "500" in err_msg
                    or "internal" in err_msg
                    or "502" in err_msg
                    or "504" in err_msg
                    or "bad gateway" in err_msg
                    or "gateway timeout" in err_msg
                )
                if is_recoverable and attempt_idx + 1 < len(models_to_try):
                    next_model = models_to_try[attempt_idx + 1]
                    import sys
                    sys.stderr.write(
                        f"[GoogleClient] Model '{candidate_model}' returned transient error ({exc}). "
                        f"Auto-falling back to '{next_model}'...\n"
                    )
                    await asyncio.sleep(0.5)
                    continue

                self._handle_exception(exc)

    def _format_messages(self, types_module: Any, messages: List[Dict[str, Any]]) -> List[Any]:
        """Converts generic chat history into Gemini contents format with function call & response support."""
        contents: List[Any] = []
        call_name_map: Dict[str, str] = {}

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts: List[Any] = []

            if role == "tool":
                call_id = msg.get("tool_call_id") or msg.get("call_id") or ""
                fn_name = call_name_map.get(call_id, "tool_result")
                parts.append(
                    types_module.Part.from_function_response(
                        name=fn_name,
                        response={"output": str(content)},
                    )
                )
                contents.append(types_module.Content(role="user", parts=parts))
                continue

            if content:
                parts.append(types_module.Part.from_text(text=str(content)))

            tool_calls = msg.get("tool_calls") or []
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw": args}
                if tc.get("id"):
                    call_name_map[tc["id"]] = fn_name

                thought_sig = tc.get("thought_signature")
                if isinstance(thought_sig, str):
                    thought_sig = thought_sig.encode("utf-8")
                elif not thought_sig:
                    thought_sig = b"\x00"

                parts.append(types_module.Part(
                    function_call=types_module.FunctionCall(name=fn_name, args=args),
                    thought_signature=thought_sig,
                ))

            if parts:
                mapped_role = "model" if role in ("assistant", "model") else "user"
                contents.append(types_module.Content(role=mapped_role, parts=parts))

        return contents

    def _build_config(self, types_module: Any, system_prompt: str, tools: Optional[List[Dict[str, Any]]]) -> Any:
        """Constructs GenerateContentConfig with temperature and optional system instruction."""
        config_kwargs: Dict[str, Any] = {
            "temperature": self.temperature,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        if tools:
            declarations: List[Dict[str, Any]] = []
            for t in tools:
                if "function" in t:
                    fn = t["function"]
                    declarations.append({
                        "name": fn.get("name"),
                        "description": fn.get("description"),
                        "parameters": fn.get("parameters"),
                    })
                elif "name" in t:
                    declarations.append(t)
            if declarations:
                config_kwargs["tools"] = [types_module.Tool(function_declarations=declarations)]

        return types_module.GenerateContentConfig(**config_kwargs)

    def _handle_exception(self, exc: Exception) -> None:
        """Categorizes and re-raises provider-specific errors into standard typed exceptions."""
        err_msg = str(exc).lower()
        if "429" in err_msg or "quota" in err_msg or "resource_exhausted" in err_msg:
            raise QuotaExceededError(f"Gemini quota exceeded: {exc}") from exc
        if "401" in err_msg or "403" in err_msg or "api_key" in err_msg or "permission" in err_msg:
            raise AuthenticationError(f"Gemini authentication failed: {exc}") from exc
        raise ProviderConnectionError(f"Gemini streaming error: {exc}") from exc

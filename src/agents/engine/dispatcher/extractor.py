"""Intent extractor parsing agent turn responses into standardized ToolCallIntents."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Sequence

from src.agents.contracts import ToolCallIntent
from src.models.types import ToolCallChunk


class IntentExtractor:
    """Extracts standardized ToolCallIntents from varied agent response payloads."""

    def extract(self, response: Any) -> List[ToolCallIntent]:
        """Extracts tool call intents from previous turn responses."""
        if response is None:
            return []
        if isinstance(response, ToolCallIntent):
            return [response]
        if isinstance(response, dict):
            return self._extract_from_dict(response)
        if isinstance(response, list):
            return self._extract_from_sequence(response)
        if isinstance(response, str):
            return self._extract_from_string(response)
        if hasattr(response, "tool_calls"):
            return self.extract(getattr(response, "tool_calls"))
        return []

    def _extract_from_dict(self, data: Dict[str, Any]) -> List[ToolCallIntent]:
        if "tool_calls" in data and isinstance(data["tool_calls"], list):
            return self._extract_from_sequence(data["tool_calls"])
        if "function_call" in data and isinstance(data["function_call"], dict):
            intent = self._build_from_function_dict(data["function_call"])
            return [intent] if intent else []
        if "name" in data and ("arguments" in data or "parameters" in data):
            intent = self._build_from_function_dict(data)
            return [intent] if intent else []
        return []

    def _extract_from_sequence(self, items: Sequence[Any]) -> List[ToolCallIntent]:
        intents: List[ToolCallIntent] = []
        for item in items:
            if isinstance(item, ToolCallIntent):
                intents.append(item)
            elif isinstance(item, ToolCallChunk):
                intents.append(self._build_from_chunk(item))
            elif isinstance(item, dict):
                intent = self._build_from_item_dict(item)
                if intent:
                    intents.append(intent)
        return intents

    def _extract_from_string(self, text: str) -> List[ToolCallIntent]:
        clean = text.strip()
        if not (clean.startswith("{") or clean.startswith("[")):
            return []
        try:
            parsed = json.loads(clean)
            return self.extract(parsed)
        except json.JSONDecodeError:
            return []

    def _build_from_item_dict(self, item: Dict[str, Any]) -> Optional[ToolCallIntent]:
        call_id = item.get("id") or item.get("call_id") or f"call_{uuid.uuid4().hex[:8]}"
        fn_data = item.get("function") if isinstance(item.get("function"), dict) else item
        tool_name = fn_data.get("name") or fn_data.get("tool_name", "")
        if not tool_name:
            return None
        args = self._normalize_arguments(fn_data.get("arguments") or fn_data.get("parameters"))
        return ToolCallIntent(call_id=call_id, tool_name=tool_name, arguments=args)

    def _build_from_function_dict(self, fn_data: Dict[str, Any]) -> Optional[ToolCallIntent]:
        tool_name = fn_data.get("name") or fn_data.get("tool_name", "")
        if not tool_name:
            return None
        call_id = fn_data.get("id") or f"call_{uuid.uuid4().hex[:8]}"
        args = self._normalize_arguments(fn_data.get("arguments") or fn_data.get("parameters"))
        return ToolCallIntent(call_id=call_id, tool_name=tool_name, arguments=args)

    def _build_from_chunk(self, chunk: ToolCallChunk) -> ToolCallIntent:
        call_id = chunk.call_id or f"call_{uuid.uuid4().hex[:8]}"
        args = self._normalize_arguments(chunk.arguments_json)
        return ToolCallIntent(
            call_id=call_id,
            tool_name=chunk.tool_name,
            arguments=args,
            thought_signature=chunk.thought_signature,
        )

    def _normalize_arguments(self, raw_args: Any) -> Dict[str, Any]:
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                return parsed if isinstance(parsed, dict) else {"raw": parsed}
            except json.JSONDecodeError:
                return {"raw_arguments": raw_args}
        return {}

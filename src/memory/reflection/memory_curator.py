"""Asynchronous Cognitive Memory Curator for Layer 5."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.memory.contracts import ReflectionAction
from src.memory.reflection.curator_prompts import REFLECTION_SYSTEM_PROMPT
from src.models.base import BaseLLMClient
from src.models.factory import ModelFactory

logger = logging.getLogger(__name__)


class MemoryReflectionAgent:
    """Intelligently reflects on turn interactions to curate long-term memory."""

    def __init__(
        self,
        model_client: Optional[BaseLLMClient] = None,
        model_name: Optional[str] = None,
    ) -> None:
        self._model_client = model_client
        if model_name:
            self._model_name = model_name
        else:
            try:
                from src.agents.factory import load_system_config
                cfg = load_system_config()
                self._model_name = cfg.get("default_model", "google:gemini-3.5-flash")
            except Exception:
                self._model_name = "google:gemini-3.5-flash"

    @property
    def model_client(self) -> Optional[BaseLLMClient]:
        if self._model_client is None:
            try:
                self._model_client = ModelFactory.get_client(
                    model_id=self._model_name,
                    temperature=0.0,
                )
            except Exception as exc:
                logger.warning("Could not initialize reflection LLM client: %s", exc)
        return self._model_client

    async def evaluate_interaction(
        self,
        user_prompt: str,
        assistant_response: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ReflectionAction]:
        """Analyzes a turn transcript and returns proposed memory mutation actions."""
        client = self.model_client
        if client is None:
            return []

        u_text = user_prompt.strip()
        a_text = assistant_response.strip()

        if not u_text and not a_text:
            return []

        prompt_content = f"### User Prompt:\n{u_text}\n\n### Assistant Response:\n{a_text}"
        if recent_history:
            history_snippets = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent_history[-3:]]
            prompt_content = f"### Context History:\n" + "\n".join(history_snippets) + "\n\n" + prompt_content

        try:
            response_text = await client.generate(
                system_prompt=REFLECTION_SYSTEM_PROMPT,
                user_prompt=prompt_content,
            )
            return self._parse_reflection_response(response_text)
        except Exception as exc:
            logger.warning("Memory reflection failed gracefully: %s", exc)
            return []

    def _parse_reflection_response(self, raw_json_text: str) -> List[ReflectionAction]:
        """Parses model JSON output into structured ReflectionAction objects with fence stripping."""
        if not raw_json_text:
            return []

        text = raw_json_text.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            candidate_json = fence_match.group(1).strip()
        else:
            brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
            candidate_json = brace_match.group(1).strip() if brace_match else text

        try:
            data = json.loads(candidate_json)
        except Exception:
            return []

        raw_actions = data.get("actions", [])
        if not isinstance(raw_actions, list):
            return []

        actions: List[ReflectionAction] = []
        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            act_type = str(item.get("action_type", "")).strip().lower()
            if act_type in ("update_profile", "store_fact", "supersede_fact", "delete_fact"):
                cat = str(item.get("category", "note")).strip().lower()
                if cat not in ("project", "system", "conversation", "note"):
                    cat = "note"
                actions.append(
                    ReflectionAction(
                        action_type=act_type,
                        section=item.get("section"),
                        key=item.get("key"),
                        value=item.get("value"),
                        content=item.get("content"),
                        category=cat,
                        tags=item.get("tags") or [],
                        target_id=item.get("target_id"),
                        reason=item.get("reason"),
                    )
                )

        return actions

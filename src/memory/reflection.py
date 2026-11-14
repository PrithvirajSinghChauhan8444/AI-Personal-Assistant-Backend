"""Asynchronous Cognitive Memory Reflection Agent for Layer 5."""

import json
import logging
from typing import Any, Dict, List, Optional

from src.memory.contracts import ReflectionAction
from src.models.base import BaseLLMClient
from src.models.factory import ModelFactory

logger = logging.getLogger(__name__)

REFLECTION_SYSTEM_PROMPT = """You are the Cognitive Memory Curator of an AI Personal Assistant.
Your sole mission is to analyze recent conversational interactions and discern what, if anything, should be preserved into long-term personal memory.

### Cognitive Selection Guidelines
1. Be Highly Selective (Anti-Slop):
   - Only preserve DURABLE personal knowledge, user preferences, explicit identity facts, habits, permanent rules, or important personal notes.
   - REJECT transient conversation, one-off questions ("what's the weather today?"), conversational filler ("thanks", "ok"), and temporary scratchpad details.
2. Determine Action Target:
   - "update_profile": Use when the user states a direct identity attribute, personal rule, coding style, or communication preference.
     * Allowed sections: "Identity", "Preferences and Rules", "Personal Context".
   - "store_fact": Use for discrete factual knowledge, notes, or long-term details.
     * Allowed categories: "project", "system", "conversation", "note".
   - "noop": Use when the conversation contains NO durable personal knowledge or when all mentioned facts are transient.
3. Strict Output Schema:
   You MUST output ONLY a valid JSON object matching this schema:
   {
     "reasoning": "<1-2 sentences explaining why this information is or isn't durable>",
     "actions": [
       {
         "action_type": "update_profile" | "store_fact" | "noop",
         "section": "<Section name, required if update_profile>",
         "key": "<Key name, required if update_profile>",
         "value": "<Value text, required if update_profile>",
         "content": "<Atomic factual sentence, required if store_fact>",
         "category": "project" | "system" | "conversation" | "note",
         "tags": ["<tag1>", "<tag2>"]
       }
     ]
   }
   If nothing is durable, return {"reasoning": "No durable information", "actions": [{"action_type": "noop"}]}.
"""


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
                self._model_name = cfg.get("default_model", "google:gemini-3.5-flash-lite")
            except Exception:
                self._model_name = "google:gemini-3.5-flash-lite"

    @property
    def model_client(self) -> Optional[BaseLLMClient]:
        if self._model_client is None:
            try:
                self._model_client = ModelFactory.get_client(
                    model_id=self._model_name,
                    temperature=0.0,
                )
            except Exception as exc:
                logger.warning(f"Could not initialize reflection LLM client: {exc}")
        return self._model_client

    async def evaluate_interaction(
        self,
        user_prompt: str,
        assistant_response: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ReflectionAction]:
        """Analyzes a turn transcript and returns memory mutation actions."""
        client = self.model_client
        if client is None:
            return []

        # Clean text
        u_text = user_prompt.strip()
        a_text = assistant_response.strip()

        # If turn is completely empty, skip LLM call
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
            logger.warning(f"Memory reflection failed gracefully: {exc}")
            return []

    def _parse_reflection_response(self, raw_json_text: str) -> List[ReflectionAction]:
        """Parses model JSON output into structured ReflectionAction objects."""
        if not raw_json_text:
            return []

        text = raw_json_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
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
            if act_type in ("update_profile", "store_fact"):
                actions.append(
                    ReflectionAction(
                        action_type=act_type,
                        section=item.get("section"),
                        key=item.get("key"),
                        value=item.get("value"),
                        content=item.get("content"),
                        category=item.get("category", "note"),
                        tags=item.get("tags") or [],
                        reason=data.get("reasoning", ""),
                    )
                )

        return actions

"""System prompt management and loading for BaseAgent."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Optional, Union


class PromptManager:
    """Manages prompt text, dynamic substitution, and filesystem resolution."""

    def __init__(
        self,
        initial_prompt: Optional[str] = None,
        owner_class: Optional[type] = None,
        agent_name: Optional[str] = None,
    ) -> None:
        self._prompt = initial_prompt.strip() if initial_prompt else ""
        if not self._prompt and owner_class:
            self._prompt = self.resolve_default_prompt(owner_class, agent_name)

    def validate(self) -> None:
        """Validates that a non-empty system prompt is configured."""
        if not self._prompt or not self._prompt.strip():
            raise ValueError("System prompt cannot be empty")

    def get_prompt(self) -> str:
        """Returns the current system prompt."""
        return self._prompt

    def set_prompt(self, prompt: str) -> None:
        """Updates the system prompt. Raises ValueError if empty."""
        if not prompt or not prompt.strip():
            raise ValueError("System prompt cannot be empty")
        self._prompt = prompt.strip()

    def format_prompt(self, **kwargs: Any) -> str:
        """Returns a formatted copy of the system prompt."""
        return self._prompt.format(**kwargs)

    @staticmethod
    def load_from_file(prompt_path: Union[str, Path], fallback: str = "") -> str:
        """Loads prompt text from disk with safe fallback."""
        target = Path(prompt_path)
        if target.is_file():
            try:
                content = target.read_text(encoding="utf-8").strip()
                if content:
                    return content
            except OSError:
                pass
        return fallback

    @classmethod
    def resolve_default_prompt(
        cls,
        owner_class: type,
        agent_name: Optional[str] = None,
    ) -> str:
        """Attempts to discover and load system prompt by convention:
        1. Sibling prompts module (e.g. get_<name>_prompt() or get_system_prompt() or get_base_prompt())
        2. prompt.md in owner class directory
        3. Fallback string
        """
        module_name = getattr(owner_class, "__module__", "")
        cls_module = sys.modules.get(module_name)
        parent_dir: Optional[Path] = None

        if cls_module and hasattr(cls_module, "__file__") and cls_module.__file__:
            parent_dir = Path(cls_module.__file__).resolve().parent

        # 1. Try importing sibling prompts module if part of a package
        if "." in module_name:
            pkg_name = module_name.rsplit(".", 1)[0]
            try:
                prompts_mod = importlib.import_module(f"{pkg_name}.prompts")
                name_clean = (agent_name or "").lower().replace("-", "_")
                getter_candidates = [
                    f"get_{name_clean}_prompt",
                    "get_system_prompt",
                    "get_base_prompt",
                    "get_prompt",
                ]
                for candidate in getter_candidates:
                    func = getattr(prompts_mod, candidate, None)
                    if callable(func):
                        prompt_res = func()
                        if isinstance(prompt_res, str) and prompt_res.strip():
                            return prompt_res.strip()

                const_candidates = [
                    f"{name_clean.upper()}_AGENT_PROMPT",
                    f"{name_clean.upper()}_PROMPT",
                    "SYSTEM_PROMPT",
                    "DEFAULT_PROMPT",
                ]
                for const_name in const_candidates:
                    val = getattr(prompts_mod, const_name, None)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
            except (ImportError, Exception):
                pass

        # 2. Try loading prompt.md in owner class directory
        if parent_dir and parent_dir.is_dir():
            cand = parent_dir / "prompt.md"
            loaded = cls.load_from_file(cand)
            if loaded:
                return loaded

        # 3. Fallback string
        name_display = agent_name or owner_class.__name__
        return f"You are {name_display}, a specialist agent."

"""Multi-provider LLM Factory for Layer 7 Model Engine."""

import os
from typing import Any, Optional

from .base import BaseLLMClient
from .providers.anthropic import AnthropicClient
from .providers.google import GoogleClient
from .providers.ollama import OllamaClient
from .providers.openai import OpenAIClient
from .types import ModelNotFoundError


class ModelFactory:
    """Factory instantiating appropriate BaseLLMClient based on model string prefixes or environment."""

    DEFAULT_FALLBACK_MODEL = "google:gemini-2.5-flash"

    @classmethod
    def get_client(
        cls,
        model_id: Optional[str] = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> BaseLLMClient:
        """Instantiates and returns a concrete BaseLLMClient.

        Args:
            model_id: Model identifier (e.g. 'google:gemini-2.5-flash', 'openai:gpt-4o',
                      'anthropic:claude-3-7-sonnet', 'ollama:llama3.2').
            temperature: Sampling temperature.
            **kwargs: Extra parameters passed to the underlying provider client.

        Returns:
            BaseLLMClient: Configured provider client.

        Raises:
            ModelNotFoundError: When the prefix or provider cannot be identified.
        """
        raw_id = (model_id or os.environ.get("DEFAULT_MODEL") or os.environ.get("GEMINI_MODEL") or cls.DEFAULT_FALLBACK_MODEL).strip()
        provider, model_name = cls._parse_model_identifier(raw_id)

        if provider == "google":
            return GoogleClient(model_name=model_name, temperature=temperature, **kwargs)
        if provider == "openai":
            return OpenAIClient(model_name=model_name, temperature=temperature, **kwargs)
        if provider == "anthropic":
            return AnthropicClient(model_name=model_name, temperature=temperature, **kwargs)
        if provider == "ollama":
            return OllamaClient(model_name=model_name, temperature=temperature, **kwargs)

        raise ModelNotFoundError(f"Unsupported model provider '{provider}' for identifier '{raw_id}'")

    @classmethod
    def _parse_model_identifier(cls, model_id: str) -> tuple[str, str]:
        """Extracts provider name and stripped model name."""
        if ":" in model_id:
            prefix, name = model_id.split(":", 1)
            prefix = prefix.lower().strip()
            name = name.strip()

            if prefix in ("google", "gemini"):
                return "google", name
            if prefix in ("openai", "gpt"):
                return "openai", name
            if prefix in ("anthropic", "claude"):
                return "anthropic", name
            if prefix == "ollama":
                return "ollama", name

            return prefix, name

        # If no colon prefix, inspect default MODEL_PROVIDER env var
        env_provider = os.environ.get("MODEL_PROVIDER", "google").lower().strip()
        return env_provider, model_id

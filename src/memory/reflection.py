"""Cognitive Memory Reflection Agent (Backward-compatibility wrapper)."""

from src.memory.reflection.curator_prompts import REFLECTION_SYSTEM_PROMPT
from src.memory.reflection.memory_curator import MemoryReflectionAgent

__all__ = ["MemoryReflectionAgent", "REFLECTION_SYSTEM_PROMPT"]

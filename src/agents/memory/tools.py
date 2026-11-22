"""Tool definitions exposed to the Memory Worker Agent."""

from typing import List

from src.agents.contracts import ToolDefinition
from src.memory.tools.tool_definitions import LEGACY_MEMORY_TOOLS, VAULT_MEMORY_TOOLS

# The Memory Agent is equipped with universal vault tools and backward-compatible legacy tools.
MEMORY_WORKER_TOOLS: List[ToolDefinition] = list(VAULT_MEMORY_TOOLS) + list(LEGACY_MEMORY_TOOLS)

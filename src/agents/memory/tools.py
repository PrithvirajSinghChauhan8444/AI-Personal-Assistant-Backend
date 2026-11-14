"""Tool definitions exposed to the Memory Worker Agent."""

from typing import List

from src.agents.contracts import ToolDefinition
from src.memory.tools import MEMORY_TOOLS

# The Memory Agent is equipped exclusively with cognitive memory management tools.
MEMORY_WORKER_TOOLS: List[ToolDefinition] = list(MEMORY_TOOLS)

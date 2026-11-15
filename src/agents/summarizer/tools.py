"""Tool definitions for SummarizerAgent.

The Summarizer Agent is a dedicated cognitive synthesizer with zero leaf tools.
It directly synthesizes subtask execution outputs into clean, human-readable markdown.
"""

from typing import List

from src.agents.contracts import ToolDefinition

# Zero leaf tools: pure cognitive synthesis directly before the gateway
SUMMARIZER_TOOLS: List[ToolDefinition] = []

"""Tool definitions for ResearchAgent (re-exported from AgentTools).

This file provides backward compatibility for modules importing from
`src.agents.research.tools`. All canonical definitions and implementations
now reside in `src.agents.research.AgentTools.tools`.
"""

from src.agents.research.AgentTools.tools import (
    RESEARCH_TOOLS,
    RESEARCH_TOOLS_REGISTRY,
    enrich_prompt_with_tools,
    get_research_local_handlers,
    get_research_tool_definitions,
    get_research_tools,
    register_research_tool,
    research_calculate,
    research_extract_keywords,
    research_format_citations,
)

__all__ = [
    "RESEARCH_TOOLS",
    "RESEARCH_TOOLS_REGISTRY",
    "enrich_prompt_with_tools",
    "get_research_local_handlers",
    "get_research_tool_definitions",
    "get_research_tools",
    "register_research_tool",
    "research_calculate",
    "research_extract_keywords",
    "research_format_citations",
]

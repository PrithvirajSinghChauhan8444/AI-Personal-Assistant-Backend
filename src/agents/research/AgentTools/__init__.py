"""AgentTools package for ResearchAgent.

Encapsulates all tools used by the Research Worker:
- tools.go: Go-native implementations (NetSearch, NetFetch, NetWeather)
- tools.py: Python tool implementations, schemas, and dynamic loaders
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

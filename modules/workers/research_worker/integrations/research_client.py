from typing import Optional
from src.CoreFunctions.SharedTools import extreme_research_tool, deep_research_tool, web_search_tool

def run_extreme_research(goal: str, time_limit_minutes: int = 20) -> str:
    """Executes multi-agent council extreme research."""
    return str(extreme_research_tool.invoke({"goal": goal, "time_limit_minutes": time_limit_minutes}))

def run_deep_research(goal: str, max_depth: int = 3) -> str:
    """Executes single-agent recursive deep research."""
    return str(deep_research_tool.invoke({"goal": goal, "max_depth": max_depth}))

def run_web_search(query: str, max_results: int = 5) -> str:
    """Executes fast web search."""
    return str(web_search_tool.invoke({"query": query, "max_results": max_results}))

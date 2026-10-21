from langchain_core.tools import tool
from modules.workers.research_worker.integrations.research_client import (
    run_extreme_research as _extreme,
    run_deep_research as _deep,
    run_web_search as _search
)

@tool
def extreme_research(goal: str, time_limit_minutes: int = 20) -> str:
    """Executes an exhaustive multi-agent council research session across all major perspectives (Technical, Market, Academic, Community). Saves full reports to disk."""
    return _extreme(goal=goal, time_limit_minutes=time_limit_minutes)

@tool
def deep_research(goal: str, max_depth: int = 3) -> str:
    """Executes iterative recursive web crawls and compiles a comprehensive research report with sources."""
    return _deep(goal=goal, max_depth=max_depth)

@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Performs a fast online search and returns relevant information with citations."""
    return _search(query=query, max_results=max_results)

research_tools = [extreme_research, deep_research, web_search]

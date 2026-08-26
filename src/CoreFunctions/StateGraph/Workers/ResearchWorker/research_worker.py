from typing import List
from src.CoreFunctions.StateGraph.worker_framework import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.ResearchWorker.research_prompt import SYSTEM_PROMPT
from src.CoreFunctions.SharedTools import human_intervention_tool, web_search_tool
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools.browser_worker_tool_navigate import browser_navigate_tool
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools.browser_worker_tool_get_page_content import (
    browser_read_page_content_tool,
    browser_read_current_page_tool,
    browser_go_back_tool
)
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools.browser_worker_tool_scroll import browser_scroll_tool

research_tools = [
    web_search_tool,
    browser_navigate_tool,
    browser_read_page_content_tool,
    browser_read_current_page_tool,
    browser_go_back_tool,
    browser_scroll_tool,
    human_intervention_tool
]

@WorkerRegistry.register
class ResearchWorker(BaseWorker):
    name = "ResearchWorker"
    description = "Conducts deep, iterative, goal-oriented web and literature research by querying search tools and reading webpages in a loop."
    instructions = SYSTEM_PROMPT
    tools = research_tools
    categories = ["research", "information-retrieval", "deep-search", "ResearchWorker"]

    @property
    def routing_rules(self) -> List[str]:
        return [
            "**Deep Research & In-Depth Information Gathering**:\n   - Any requests asking for deep, comprehensive, or detailed research, exhaustive reports, literature reviews, or iterative searches across multiple websites should be routed to ResearchWorker. ResearchWorker will handle the research loop until the goal is fully answered."
        ]

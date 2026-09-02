from typing import List
from src.CoreFunctions.StateGraph.worker_framework import BaseWorker, WorkerRegistry
from src.CoreFunctions.StateGraph.Workers.ResearchWorker.research_prompt import (
    SYSTEM_PROMPT,
    EXTREME_RESEARCH_PROMPT,
    DEEP_RESEARCH_PROMPT,
    NORMAL_RESEARCH_PROMPT,
    get_research_prompt,
    is_extreme_research,
    is_deep_research
)
from src.CoreFunctions.SharedTools import (
    human_intervention_tool,
    web_search_tool,
    deep_research_tool,
    extreme_research_tool
)
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools.browser_worker_tool_navigate import browser_navigate_tool
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools.browser_worker_tool_get_page_content import (
    browser_read_page_content_tool,
    browser_read_current_page_tool,
    browser_go_back_tool
)
from src.CoreFunctions.StateGraph.Workers.BrowserWorker.browser_worker_tools.browser_worker_tool_scroll import browser_scroll_tool

research_tools = [
    extreme_research_tool,
    deep_research_tool,
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
    description = (
        "Conducts web and academic research across three modes: "
        "1) Extreme Research (multi-agent council investigation governed by time limits with per-agent notes and lossless master report), "
        "2) Deep Research (single-agent recursive multi-depth crawl and comprehensive report), and "
        "3) Normal/Small Research (fast MCP web search without opening browsers)."
    )
    instructions = SYSTEM_PROMPT
    tools = research_tools
    categories = ["research", "information-retrieval", "extreme-search", "deep-search", "web-search", "ResearchWorker"]

    def get_instructions(self) -> str:
        """Base instructions for ResearchWorker."""
        return SYSTEM_PROMPT

    def get_task_instruction(self, task_desc: str) -> str:
        """Dynamically returns only the prompt required for the specific research mode."""
        return get_research_prompt(task_desc)

    @property
    def routing_rules(self) -> List[str]:
        return [
            "**Research & Information Gathering (Extreme vs Deep vs Normal Research)**:\n"
            "   - **Extreme Research Mode (Council)**: Route tasks asking for 360-degree multi-perspective investigations, multi-agent council research, extreme deep dives with time budgets, market+tech+academic comparative studies, or tasks explicitly mentioning 'extreme research' or 'council research' to ResearchWorker (it will run `extreme_research` spanning specialized agents, saving individual files and producing a lossless master report).\n"
            "   - **Deep Research Mode**: Route tasks asking for in-depth, exhaustive, comprehensive research, full research reports, literature reviews, or recursive investigations to ResearchWorker (it will run recursive `deep_research` and save a full report with sources to disk).\n"
            "   - **Small / Normal Research Mode**: Route tasks asking for quick lookups, small/normal research, factual questions, current news/updates, or brief overviews to ResearchWorker (it will perform fast MCP web search without launching browser windows and return concise outputs with source links)."
        ]

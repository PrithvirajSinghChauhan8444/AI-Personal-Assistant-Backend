from src.CoreFunctions.SharedTools import human_intervention_tool, web_search_tool
from src.CoreFunctions.StateGraph.Workers.MemoryWorker.memory_worker_tools import memory_worker_tool_remember, memory_worker_tool_recall
from .browser_worker_tool_navigate import browser_navigate_tool
from .browser_worker_tool_click import browser_click_tool, browser_click_selector_tool
from .browser_worker_tool_type_text import browser_input_tool, browser_input_selector_tool
from .browser_worker_tool_get_page_content import browser_read_page_content_tool, browser_read_current_page_tool, browser_go_back_tool
from .browser_worker_tool_screenshot import browser_screenshot_tool

browser_tools = [
    browser_navigate_tool,
    browser_click_tool,
    browser_click_selector_tool,
    browser_input_tool,
    browser_input_selector_tool,
    browser_go_back_tool,
    browser_read_current_page_tool,
    browser_read_page_content_tool,
    web_search_tool,
    memory_worker_tool_remember,
    memory_worker_tool_recall,
    human_intervention_tool
]

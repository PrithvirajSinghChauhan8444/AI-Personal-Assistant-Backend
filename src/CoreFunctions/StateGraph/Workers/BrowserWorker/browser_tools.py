from langchain_core.tools import StructuredTool
from src.CoreFunctions.tools import (
    request_human_intervention_sync, request_human_intervention,
    browser_navigate, browser_click, browser_click_selector,
    browser_input, browser_input_selector, browser_go_back,
    browser_read_current_page, browser_read_page_content,
    web_search
)

human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)

browser_tools = [
    StructuredTool.from_function(name="browser_navigate", description="Navigate to a URL and return interactive elements", coroutine=browser_navigate),
    StructuredTool.from_function(name="browser_click", description="Click an element by its numerical data-agent-id", coroutine=browser_click),
    StructuredTool.from_function(name="browser_click_selector", description="Click an element using a CSS/XPath selector", coroutine=browser_click_selector),
    StructuredTool.from_function(name="browser_input", description="Input text into an element by its numerical data-agent-id", coroutine=browser_input),
    StructuredTool.from_function(name="browser_input_selector", description="Input text into an element using a CSS/XPath selector", coroutine=browser_input_selector),
    StructuredTool.from_function(name="browser_go_back", description="Navigate back to the previous page", coroutine=browser_go_back),
    StructuredTool.from_function(name="browser_read_current_page", description="Read the current active tab's URL, page title, and interactive elements without navigating", coroutine=browser_read_current_page),
    StructuredTool.from_function(name="browser_read_page_content", description="Read or query the textual content (paragraphs, headings) of the current page in chunks or using a local LLM summary/query mode", coroutine=browser_read_page_content),
    StructuredTool.from_function(web_search),
    human_intervention_tool,
]

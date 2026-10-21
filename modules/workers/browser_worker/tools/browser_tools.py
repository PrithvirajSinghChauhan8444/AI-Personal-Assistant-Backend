from typing import Optional, Union
from langchain_core.tools import tool
from modules.workers.browser_worker.integrations import browser_client

@tool
def browser_navigate(url: str) -> str:
    """Navigates the browser to the specified URL."""
    return browser_client.navigate_to_url(url)

@tool
def browser_get_dom_map() -> str:
    """Inspects and returns numbered interactive elements, buttons, inputs, and links on the active page."""
    return browser_client.get_dom_map()

@tool
def browser_click(element_index: Union[int, str]) -> str:
    """Clicks on an interactive element by numeric index (e.g. 1) or CSS selector."""
    return browser_client.click_element(element_index)

@tool
def browser_input(element_index: Union[int, str], text: str, press_enter: bool = False) -> str:
    """Types text into an input field by numeric index (e.g. 2) or CSS selector."""
    return browser_client.type_text(element_index, text, press_enter=press_enter)

@tool
def browser_scroll(direction: str = "down", amount: int = 500) -> str:
    """Scrolls the current web page 'up' or 'down'."""
    return browser_client.scroll_page(direction=direction, amount=amount)

@tool
def browser_read_content(max_chars: int = 4000) -> str:
    """Reads visible text content from the current active page."""
    return browser_client.get_page_content(max_chars=max_chars)

@tool
def browser_screenshot(filename: Optional[str] = None) -> str:
    """Captures a screenshot of the active web page."""
    return browser_client.take_screenshot(filename)

browser_tools = [
    browser_navigate,
    browser_get_dom_map,
    browser_click,
    browser_input,
    browser_scroll,
    browser_read_content,
    browser_screenshot
]

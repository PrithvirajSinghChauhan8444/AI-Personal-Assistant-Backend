"""Playwright browser manager and web automation integrations for browser_worker."""
from .browser_client import (
    navigate_to_url,
    click_element,
    type_text,
    scroll_page,
    take_screenshot,
    get_page_content,
    get_dom_map,
    close_browser
)

__all__ = [
    "navigate_to_url",
    "click_element",
    "type_text",
    "scroll_page",
    "take_screenshot",
    "get_page_content",
    "get_dom_map",
    "close_browser"
]

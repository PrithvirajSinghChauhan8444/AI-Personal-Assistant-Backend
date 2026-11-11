"""Tool definitions for BrowserAgent."""

from typing import List

from src.agents.contracts import ToolDefinition

BROWSER_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="browser_navigate",
        category="browser",
        description="Navigates to a target URL in the browser and waits for the page to load.",
        risk="LOW",
        prompt_usage_tip="Always check page content after navigation to confirm successful load.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full HTTP/HTTPS URL to open"},
            },
            "required": ["url"],
        },
    ),
    ToolDefinition(
        name="browser_read_content",
        category="browser",
        description="Reads the visible text, headers, and interactive DOM layout of the current browser page.",
        risk="LOW",
        prompt_usage_tip="Use to inspect page text, articles, or locate buttons/links for subsequent clicks.",
        parameters={
            "type": "object",
            "properties": {
                "max_length": {"type": "integer", "description": "Maximum characters to return (default: 4000)", "default": 4000},
            },
        },
    ),
    ToolDefinition(
        name="browser_click",
        category="browser",
        description="Clicks an interactive button, link, or element on the current page.",
        risk="MEDIUM",
        prompt_usage_tip="Specify an accessible text label or standard CSS selector.",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or element identifier to click"},
            },
            "required": ["selector"],
        },
    ),
    ToolDefinition(
        name="browser_type",
        category="browser",
        description="Types text into an active form input or search field.",
        risk="MEDIUM",
        prompt_usage_tip="Use to submit queries, enter filters, or fill forms.",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector of the input field"},
                "text": {"type": "string", "description": "Text string to type"},
                "press_enter": {"type": "boolean", "description": "Whether to press Enter after typing", "default": False},
            },
            "required": ["selector", "text"],
        },
    ),
    ToolDefinition(
        name="browser_scroll",
        category="browser",
        description="Scrolls the browser viewport up or down to load lazy content.",
        risk="LOW",
        prompt_usage_tip="Use to reveal content below the fold.",
        parameters={
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["down", "up"], "description": "Scroll direction", "default": "down"},
                "amount": {"type": "integer", "description": "Pixels to scroll (default: 600)", "default": 600},
            },
        },
    ),
    ToolDefinition(
        name="browser_screenshot",
        category="browser",
        description="Captures a visual screenshot of the current page viewport or element.",
        risk="LOW",
        prompt_usage_tip="Use to visually verify web dashboards, graphs, or UI errors.",
        parameters={
            "type": "object",
            "properties": {
                "full_page": {"type": "boolean", "description": "Capture entire scrollable page", "default": False},
            },
        },
    ),
]

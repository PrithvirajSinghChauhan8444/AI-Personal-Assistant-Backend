"""Tool definitions for BrowserAgent."""

from typing import List

from src.agents.contracts import ToolDefinition

BROWSER_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="browser_navigate",
        category="browser",
        description="Navigates to a target URL in the browser and waits for the page to load.",
        risk="LOW",
        prompt_usage_tip="Always inspect page content after navigation to confirm successful load.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full HTTP/HTTPS URL to open"},
            },
            "required": ["url"],
        },
        execution_domain="mcp_bridge",
        required_capability="browser:read",
    ),
    ToolDefinition(
        name="browser_snapshot",
        category="browser",
        description="Captures accessibility tree snapshot of the page with interactive element references and roles.",
        risk="LOW",
        prompt_usage_tip="Always call after navigation to inspect buttons, links, inputs, and text content.",
        parameters={
            "type": "object",
            "properties": {},
        },
        execution_domain="mcp_bridge",
        required_capability="browser:read",
    ),
    ToolDefinition(
        name="browser_click",
        category="browser",
        description="Clicks an interactive button, link, or element on the current page.",
        risk="MEDIUM",
        prompt_usage_tip="Specify an accessible text label, element reference from snapshot, or CSS selector.",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or element text to click"},
                "target": {"type": "string", "description": "Target element ref from snapshot"},
            },
        },
        execution_domain="mcp_bridge",
        required_capability="browser:interact",
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
                "target": {"type": "string", "description": "Target element ref from snapshot"},
                "text": {"type": "string", "description": "Text string to type"},
                "press_enter": {"type": "boolean", "description": "Whether to press Enter after typing", "default": False},
            },
            "required": ["text"],
        },
        execution_domain="mcp_bridge",
        required_capability="browser:interact",
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
        execution_domain="mcp_bridge",
        required_capability="browser:read",
    ),
    ToolDefinition(
        name="browser_wait_for",
        category="browser",
        description="Waits for dynamic text to appear or disappear, or pauses for page transitions.",
        risk="LOW",
        prompt_usage_tip="Use when dynamic content takes time to render.",
        parameters={
            "type": "object",
            "properties": {
                "time": {"type": "number", "description": "Time to wait in seconds"},
                "text": {"type": "string", "description": "Text to wait for on page"},
            },
        },
        execution_domain="mcp_bridge",
        required_capability="browser:read",
    ),
    ToolDefinition(
        name="browser_take_screenshot",
        category="browser",
        description="Takes a visual PNG screenshot of the current browser page.",
        risk="LOW",
        prompt_usage_tip="Use to visually capture rendered pages or charts.",
        parameters={
            "type": "object",
            "properties": {
                "fullPage": {"type": "boolean", "description": "Whether to capture full scrollable height", "default": False},
                "filename": {"type": "string", "description": "Optional file path to save screenshot to"},
            },
        },
        execution_domain="mcp_bridge",
        required_capability="browser:read",
    ),
    ToolDefinition(
        name="browser_tabs",
        category="browser",
        description="List, create, close, or select browser tabs.",
        risk="LOW",
        prompt_usage_tip="Use to manage multiple active tabs.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "new", "close", "select"], "description": "Operation to perform"},
                "index": {"type": "number", "description": "Tab index"},
                "url": {"type": "string", "description": "URL for new tab"},
            },
            "required": ["action"],
        },
        execution_domain="mcp_bridge",
        required_capability="browser:interact",
    ),
    ToolDefinition(
        name="browser_navigate_back",
        category="browser",
        description="Navigates back to the previous page in history.",
        risk="LOW",
        prompt_usage_tip="Use to return to previous page.",
        parameters={
            "type": "object",
            "properties": {},
        },
        execution_domain="mcp_bridge",
        required_capability="browser:read",
    ),
    ToolDefinition(
        name="browser_close",
        category="browser",
        description="Closes the browser page or session.",
        risk="LOW",
        prompt_usage_tip="Use when browser automation is finished.",
        parameters={
            "type": "object",
            "properties": {},
        },
        execution_domain="mcp_bridge",
        required_capability="browser:interact",
    ),
]

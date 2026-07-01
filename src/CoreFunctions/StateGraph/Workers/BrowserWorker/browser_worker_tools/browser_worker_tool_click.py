from langchain_core.tools import StructuredTool
from .browser_manager import _get_browser_page, _human_click, _get_dom_map

async def browser_click(element_id: int, offset: int = 0, limit: int = 30) -> str:
    """Clicks an interactive element matching a specific numerical element_id.

    Args:
        element_id (int): The unique numerical ID of the element on the page.
        offset (int): Starting index of interactive elements to list. Defaults to 0.
        limit (int): Maximum number of interactive elements to return. Defaults to 30.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_click")
    print(f"   Args: element_id={element_id}, offset={offset}, limit={limit}")
    try:
        page = await _get_browser_page()
        selector = f'[data-agent-id="{element_id}"]'
        await _human_click(page, selector)
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        elements_str = await _get_dom_map(offset=offset, limit=limit)
        return elements_str
    except Exception as e:
        return f"Error clicking element [{element_id}]: {e}"

async def browser_click_selector(selector: str, offset: int = 0, limit: int = 30) -> str:
    """Clicks an element matching a CSS or text selector. Helpful if role or ID-based matching fails.

    Args:
        selector (str): The CSS selector (e.g. 'button#submit').
        offset (int): Starting index of interactive elements to list. Defaults to 0.
        limit (int): Maximum number of interactive elements to return. Defaults to 30.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_click_selector")
    print(f"   Args: selector={selector}, offset={offset}, limit={limit}")
    try:
        page = await _get_browser_page()
        await _human_click(page, selector)
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        elements_str = await _get_dom_map(offset=offset, limit=limit)
        return elements_str
    except Exception as e:
        return f"Error clicking selector '{selector}': {e}"

browser_click_tool = StructuredTool.from_function(
    func=browser_click,
    name="browser_click",
    coroutine=browser_click,
    description="Click an element by numerical ID"
)

browser_click_selector_tool = StructuredTool.from_function(
    func=browser_click_selector,
    name="browser_click_selector",
    coroutine=browser_click_selector,
    description="Click an element by CSS/XPath selector"
)

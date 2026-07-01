from langchain_core.tools import StructuredTool
from .browser_manager import _get_browser_page, _get_dom_map

async def browser_navigate(url: str, offset: int = 0, limit: int = 30) -> str:
    """Navigates the browser to the specified URL and returns its interactive elements.

    Args:
        url (str): The web address to navigate to (e.g. 'https://github.com').
        offset (int): Starting index of interactive elements to list. Defaults to 0.
        limit (int): Maximum number of interactive elements to return. Defaults to 30.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_navigate")
    print(f"   Args: url={url}, offset={offset}, limit={limit}")
    try:
        page = await _get_browser_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        elements_str = await _get_dom_map(offset=offset, limit=limit)
        print(elements_str)
        return elements_str
    except Exception as e:
        return f"Error navigating browser: {e}"

browser_navigate_tool = StructuredTool.from_function(
    func=browser_navigate,
    name="browser_navigate",
    coroutine=browser_navigate,
    description="Navigate to a URL and return interactive elements"
)

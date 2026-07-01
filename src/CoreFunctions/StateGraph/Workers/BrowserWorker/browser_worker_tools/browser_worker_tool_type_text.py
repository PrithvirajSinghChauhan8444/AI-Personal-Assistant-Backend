from langchain_core.tools import StructuredTool
from .browser_manager import _get_browser_page, _human_type, _get_dom_map

async def browser_input(element_id: int, text: str, offset: int = 0, limit: int = 30) -> str:
    """Fills a text input field matching a specific numerical element_id with text.

    Args:
        element_id (int): The unique numerical ID of the input field.
        text (str): The text string to enter.
        offset (int): Starting index of interactive elements to list. Defaults to 0.
        limit (int): Maximum number of interactive elements to return. Defaults to 30.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_input")
    print(f"   Args: element_id={element_id}, text={text}, offset={offset}, limit={limit}")
    try:
        page = await _get_browser_page()
        selector = f'[data-agent-id="{element_id}"]'
        await _human_type(page, selector, text)
        await page.wait_for_timeout(1000)
        elements_str = await _get_dom_map(offset=offset, limit=limit)
        return elements_str
    except Exception as e:
        return f"Error filling element [{element_id}]: {e}"

async def browser_input_selector(selector: str, text: str, offset: int = 0, limit: int = 30) -> str:
    """Fills an input field matching a CSS or text selector with text.

    Args:
        selector (str): The CSS or text selector of the input field.
        text (str): The text to type.
        offset (int): Starting index of interactive elements to list. Defaults to 0.
        limit (int): Maximum number of interactive elements to return. Defaults to 30.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_input_selector")
    print(f"   Args: selector={selector}, text={text}, offset={offset}, limit={limit}")
    try:
        page = await _get_browser_page()
        await _human_type(page, selector, text)
        await page.wait_for_timeout(1000)
        elements_str = await _get_dom_map(offset=offset, limit=limit)
        return elements_str
    except Exception as e:
        return f"Error filling selector '{selector}': {e}"

browser_input_tool = StructuredTool.from_function(
    func=browser_input,
    name="browser_input",
    coroutine=browser_input,
    description="Type text by numerical ID"
)

browser_input_selector_tool = StructuredTool.from_function(
    func=browser_input_selector,
    name="browser_input_selector",
    coroutine=browser_input_selector,
    description="Type text by selector"
)

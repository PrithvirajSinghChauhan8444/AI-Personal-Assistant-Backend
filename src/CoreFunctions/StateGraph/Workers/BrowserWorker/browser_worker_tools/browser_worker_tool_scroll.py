from langchain_core.tools import StructuredTool
from .browser_manager import _get_browser_page, _human_scroll, _get_dom_map

async def browser_scroll(
    direction: str = "down",
    distance: int = 300
) -> str:
    """Scrolls the current browser page in the specified direction.

    Args:
        direction (str): The direction to scroll ('down' or 'up'). Defaults to 'down'.
        distance (int): The distance in pixels to scroll. Defaults to 300.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_scroll")
    print(f"   Args: direction={direction!r}, distance={distance}")

    if direction not in ["down", "up"]:
        return f"Error: Invalid direction '{direction}'. Valid options are: 'down', 'up'."

    try:
        page = await _get_browser_page()
        await _human_scroll(page, direction=direction, distance=distance)
        
        # After scrolling, return a DOM map preview of the newly scrolled viewport
        dom_map = await _get_dom_map(offset=0, limit=30)
        return f"Successfully scrolled {direction} by {distance}px. New viewport:\n{dom_map}"
    except Exception as e:
        return f"Error scrolling browser: {e}"

browser_scroll_tool = StructuredTool.from_function(
    func=browser_scroll,
    name="browser_scroll",
    coroutine=browser_scroll,
    description=(
        "Scroll the current browser page in the specified direction (down | up) by a given distance in pixels. "
        "Returns a preview of the new viewport's DOM map."
    )
)

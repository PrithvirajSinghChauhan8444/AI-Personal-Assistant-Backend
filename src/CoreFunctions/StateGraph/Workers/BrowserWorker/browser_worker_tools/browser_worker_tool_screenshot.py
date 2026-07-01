import os
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Infrastructure.security_utils import is_path_safe
from .browser_manager import _get_browser_page

async def browser_screenshot(save_path: str = "screenshot.png") -> str:
    """Takes a screenshot of the current page viewport and saves it.
    
    Args:
        save_path (str): The local path where the screenshot will be saved.
    """
    try:
        page = await _get_browser_page()
        abs_path = os.path.abspath(save_path)
        if not is_path_safe(abs_path):
            return f"❌ Security Violation: Save path '{save_path}' is outside sandbox."
        await page.screenshot(path=abs_path)
        return f"Successfully saved screenshot to: {abs_path}"
    except Exception as e:
        return f"Error taking screenshot: {e}"

browser_screenshot_tool = StructuredTool.from_function(
    func=browser_screenshot,
    name="browser_screenshot",
    coroutine=browser_screenshot,
    description="Take a screenshot of the current page viewport"
)

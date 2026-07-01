import os
import base64
from langchain_core.tools import StructuredTool
from typing import Optional
from src.CoreFunctions.Infrastructure.security_utils import is_path_safe
from .browser_manager import _get_browser_page


def _get_vision_model():
    """Return a Gemini Flash model capable of vision (multimodal) inference."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from dotenv import load_dotenv

        # Load .env from project root
        curr = os.path.abspath(__file__)
        while curr and not os.path.exists(os.path.join(curr, "src")):
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent
        load_dotenv(os.path.join(curr, ".env"), override=True)

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None

        # Prefer a fast flash model; fall back to whatever GEMINI_MODEL is set to
        model_name = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0,
        )
    except Exception:
        return None


async def browser_screenshot(
    save_path: str = "screenshot.png",
    vision_query: Optional[str] = None
) -> str:
    """Takes a screenshot of the current page viewport and optionally queries a vision model.

    Use this as a last resort when the DOM map gives you nothing useful (canvas apps,
    image-heavy pages, games). Provide a vision_query to ask the vision model a specific
    question about the screenshot (e.g. 'where is the login button?').

    Args:
        save_path (str): Local path where the screenshot PNG will be saved.
        vision_query (str, optional): A question to ask the Gemini vision model about the
            screenshot. If omitted, only the file path is returned (backwards compatible).
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_screenshot")
    print(f"   Args: save_path={save_path}, vision_query={vision_query!r}")

    try:
        page = await _get_browser_page()
        abs_path = os.path.abspath(save_path)
        if not is_path_safe(abs_path):
            return f"❌ Security Violation: Save path '{save_path}' is outside sandbox."

        # Take screenshot as bytes (also save to disk)
        screenshot_bytes = await page.screenshot(path=abs_path, full_page=False)

        result_msg = f"Screenshot saved to: {abs_path}"

        if not vision_query:
            return result_msg

        # Encode to base64 and query vision model
        b64_image = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

        vision_model = _get_vision_model()
        if vision_model is None:
            return (
                f"{result_msg}\n\n"
                "⚠️ Vision query skipped: No GEMINI_API_KEY found or "
                "langchain-google-genai not installed."
            )

        from langchain_core.messages import HumanMessage

        message = HumanMessage(
            content=[
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                },
                {
                    "type": "text",
                    "text": (
                        f"This is a screenshot of a web page. "
                        f"Answer the following question based only on what you can see:\n\n"
                        f"{vision_query}"
                    ),
                },
            ]
        )

        try:
            response = await vision_model.ainvoke([message])
            vision_answer = response.content
        except Exception as vision_err:
            vision_answer = f"Vision model error: {vision_err}"

        return (
            f"{result_msg}\n\n"
            f"Vision query: \"{vision_query}\"\n"
            f"Vision answer: {vision_answer}"
        )

    except Exception as e:
        return f"Error taking screenshot: {e}"


browser_screenshot_tool = StructuredTool.from_function(
    func=browser_screenshot,
    name="browser_screenshot",
    coroutine=browser_screenshot,
    description=(
        "Take a screenshot of the current page. Use as a LAST RESORT when the DOM map "
        "gives no useful info (canvas apps, image-heavy pages, games). "
        "Optionally pass a vision_query (e.g. 'where is the login button?') to ask a "
        "Gemini vision model about the screenshot and get a text answer."
    )
)

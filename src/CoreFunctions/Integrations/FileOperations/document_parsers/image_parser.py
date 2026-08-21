"""
Standalone Image File Parser Module (.png, .jpg, .jpeg, .webp, .bmp).
Uses Gemini Vision LLM to extract text, describe diagrams, and interpret visual contents from standalone images.
"""

import os
import base64
from typing import Optional

def load_environment():
    """Locates and loads .env from project root, config/.env, or current working directory."""
    try:
        from dotenv import load_dotenv
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
        
        candidates = [
            os.path.join(project_root, "config", ".env"),
            os.path.join(project_root, ".env"),
            os.path.join(os.getcwd(), "config", ".env"),
            os.path.join(os.getcwd(), ".env")
        ]
        for env_path in candidates:
            if os.path.exists(env_path):
                load_dotenv(env_path, override=True)
                break
    except Exception:
        pass

def extract_image_file(filepath: str) -> str:
    """
    Reads a standalone image file and uses Gemini Vision to transcribe its text and describe its visual content.
    """
    if not os.path.exists(filepath):
        return f"❌ Error: Image file not found at '{filepath}'"

    load_environment()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        return f"❌ Error: Cannot read image '{os.path.basename(filepath)}'. Gemini Vision API key missing in config/.env"

    try:
        from src.CoreFunctions.Infrastructure.llm_factory import get_llm
        from langchain_core.messages import HumanMessage
        
        with open(filepath, "rb") as f:
            img_bytes = f.read()

        ext = filepath.split(".")[-1].lower()
        mime_type = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
        
        prompt = (
            "Analyze this image in detail. Extract all readable text, labels, titles, numbers, and tabular structures verbatim. "
            "If it contains a diagram, flowchart, UI layout, or handwritten notes, describe the layout, elements, and connections clearly."
        )

        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        llm = get_llm(model_name, temperature=0.1)
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64.b64encode(img_bytes).decode()}"}
                }
            ]
        )
        res = llm.invoke([message])
        
        if isinstance(res.content, list):
            text_parts = []
            for part in res.content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
                elif hasattr(part, "text"):
                    text_parts.append(str(part.text))
            content_str = "".join(text_parts).strip()
        else:
            content_str = str(res.content).strip()

        return f"🖼️ **Image Analysis for '{os.path.basename(filepath)}':**\n\n{content_str}"
    except Exception as e:
        return f"❌ Error analyzing image '{filepath}' with Gemini Vision: {e}"

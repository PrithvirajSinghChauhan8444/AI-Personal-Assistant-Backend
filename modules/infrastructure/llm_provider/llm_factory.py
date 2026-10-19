import os
from typing import Optional, Any
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

def load_environment():
    """Locates and loads .env from project root."""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
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
        # Disable broken LangSmith tracing to prevent 403 network spam
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
    except Exception:
        pass

def extract_text_content(content: Any) -> str:
    """Extracts raw string text from string, list of blocks, or structured LLM messages."""
    if hasattr(content, "content"):
        content = content.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(str(getattr(item, "text")))
            else:
                parts.append(str(item))
        return "".join(parts).strip()
    return str(content).strip()


def get_llm(model_name: Optional[str] = None, temperature: float = 0.0, **kwargs) -> Any:
    """Creates and returns a LangChain chat model instance dynamically based on model prefixes or config."""
    load_environment()
    provider = os.environ.get("MODEL_PROVIDER", "google").lower().strip()
    
    if model_name:
        model_name = model_name.strip()
        if model_name.startswith("google:"):
            provider = "google"
            model_name = model_name[7:]
        elif model_name.startswith("openai:"):
            provider = "openai"
            model_name = model_name[7:]
        elif model_name.startswith("groq:"):
            provider = "groq"
            model_name = model_name[5:]
        elif model_name.startswith("ollama:"):
            provider = "ollama"
            model_name = model_name[7:]

    if not model_name:
        model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

    if provider == "groq":
        return ChatGroq(model_name=model_name, temperature=temperature, **kwargs)
    elif provider == "ollama":
        return ChatOllama(model=model_name, temperature=temperature, **kwargs)
    elif provider == "openai":
        return ChatOpenAI(model=model_name, temperature=temperature, **kwargs)
    else:
        # Default Google provider
        api_key = os.environ.get("GEMINI_API_KEY")
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            **kwargs
        )

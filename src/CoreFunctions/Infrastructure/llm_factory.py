import os
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
    except Exception:
        pass

def get_llm(model_name: str = None, temperature: float = 0.0, **kwargs):
    """
    Creates and returns a LangChain chat model instance dynamically based on model prefixes or environment settings.
    
    Supported prefixes:
    - `openrouter:` (e.g., `openrouter:google/gemini-2.5-flash`)
    - `google:` (e.g., `google:gemini-3.1-flash-lite`)
    - `openai:` (e.g., `openai:gpt-4o`)
    - `groq:` (e.g., `groq:llama3-8b-8192`)
    - `ollama:` (e.g., `ollama:gemma4:e4b`)
    
    If no prefix is provided, queries the `MODEL_PROVIDER` environment variable, defaulting to `google`.
    """
    load_environment()
    
    # 1. Determine provider and clean model name
    provider = os.environ.get("MODEL_PROVIDER", "google").lower().strip()
    explicit_prefix = False
    
    if model_name:
        model_name = model_name.strip()
        
        # Check for explicit prefixes
        if model_name.startswith("openrouter:"):
            provider = "openrouter"
            model_name = model_name[11:]
            explicit_prefix = True
        elif model_name.startswith("google:"):
            provider = "google"
            model_name = model_name[7:]
            explicit_prefix = True
        elif model_name.startswith("openai:"):
            provider = "openai"
            model_name = model_name[7:]
            explicit_prefix = True
        elif model_name.startswith("groq:"):
            provider = "groq"
            model_name = model_name[5:]
            explicit_prefix = True
        elif model_name.startswith("ollama:"):
            provider = "ollama"
            model_name = model_name[7:]
            explicit_prefix = True
            
    # 2. Get default models if model_name is not provided or resolved empty
    if not model_name:
        if provider == "openrouter":
            model_name = os.environ.get("OPENROUTER_MODEL") or os.environ.get("GEMINI_MODEL") or "google/gemini-2.5-flash"
        elif provider == "openai":
            model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        elif provider == "groq":
            model_name = os.environ.get("GROQ_MODEL", "llama3-8b-8192")
        elif provider == "ollama":
            model_name = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
        else:
            model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

    # If no explicit prefix was used, and provider is the default 'google',
    # check if we should route to Ollama or Google based on the model name.
    if not explicit_prefix and provider == "google":
        if "gemini" not in model_name.lower():
            provider = "ollama"

    # If the provider is not set explicitly, but the model contains "gemini", default to google provider
    if provider not in ["openrouter", "openai", "groq", "ollama", "google"]:
        if "gemini" in model_name.lower():
            provider = "google"
        elif "gemma" in model_name.lower() or "llama" in model_name.lower():
            provider = "ollama"
        else:
            provider = "google" # fallback

    # 3. Instantiate model based on provider
    if provider == "openrouter":
        if model_name and "/" not in model_name:
            env_model = os.environ.get("OPENROUTER_MODEL", "").strip()
            if env_model:
                model_name = env_model

        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            # Fallback to general openai key
            api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        max_tokens = kwargs.pop("max_tokens", 4096)
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            default_headers={
                "HTTP-Referer": "https://github.com/PrithvirajSinghChauhan8444/AI-Personal-Assistant-Backend",
                "X-Title": "AI Personal Assistant Backend"
            },
            **kwargs
        )
        
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            temperature=temperature,
            **kwargs
        )
        
    elif provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        return ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            **kwargs
        )
        
    elif provider == "ollama":
        options = {"thinking": True} if kwargs.pop("thinking", True) else {}
        if "options" in kwargs:
            kwargs["options"].update(options)
        else:
            kwargs["options"] = options
        return ChatOllama(
            model=model_name,
            temperature=temperature,
            **kwargs
        )
        
    else: # Default: google
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GEMINI_API_KEY")
        
        # Merge thinking budget for thinking-enabled gemini models
        llm_kwargs = {}
        if "gemini" in model_name.lower():
            llm_kwargs["extra_body"] = {"thinking_config": {"thinking_budget": 2048}}
            
        if "model_kwargs" in kwargs:
            kwargs["model_kwargs"].update(llm_kwargs)
        else:
            kwargs["model_kwargs"] = llm_kwargs
            
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key,
            **kwargs
        )

import os
from dotenv import load_dotenv

# Ensure environment variables (.env) are loaded across all modular components
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from .llm_provider.llm_factory import get_llm
from .security.vault import verify_password, get_console_lock
from .storage.unified_storage import UnifiedStorage
from .observability.logger import ModuleLogger
from .observability.telemetry import TelemetryManager, get_module_tracer

__all__ = [
    "get_llm",
    "verify_password",
    "get_console_lock",
    "UnifiedStorage",
    "ModuleLogger",
    "TelemetryManager",
    "get_module_tracer"
]


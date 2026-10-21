import os
from dotenv import load_dotenv

# Ensure environment variables (.env) are loaded across all modular components
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from .llm_provider.llm_factory import get_llm
from .security.vault import verify_password, get_console_lock
from .security.oauth import (
    get_google_credentials,
    load_google_accounts,
    resolve_expected_email
)
from .storage.unified_storage import UnifiedStorage
from .storage.session_manager import (
    save_interrupted_task_checkpoint,
    clear_interrupted_task_checkpoint,
    get_interrupted_task,
    save_session_context,
    save_session_context_async,
    load_session_context,
    clear_session_context,
    archive_chat_turn,
    SESSION_CONTEXT_PATH,
    INTERRUPTED_TASK_PATH
)
from .observability.logger import ModuleLogger
from .observability.telemetry import TelemetryManager, get_module_tracer

__all__ = [
    "get_llm",
    "verify_password",
    "get_console_lock",
    "get_google_credentials",
    "load_google_accounts",
    "resolve_expected_email",
    "UnifiedStorage",
    "save_interrupted_task_checkpoint",
    "clear_interrupted_task_checkpoint",
    "get_interrupted_task",
    "save_session_context",
    "save_session_context_async",
    "load_session_context",
    "clear_session_context",
    "archive_chat_turn",
    "SESSION_CONTEXT_PATH",
    "INTERRUPTED_TASK_PATH",
    "ModuleLogger",
    "TelemetryManager",
    "get_module_tracer"
]

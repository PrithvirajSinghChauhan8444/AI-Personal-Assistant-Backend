import os
import json
import sqlite3
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

def _get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

PROJECT_ROOT = _get_project_root()
SESSION_CONTEXT_PATH = os.path.join(PROJECT_ROOT, "Memory", "session_context.json")
INTERRUPTED_TASK_PATH = os.path.join(PROJECT_ROOT, "Memory", "interrupted_task.json")
CHAT_ARCHIVE_PATH = os.path.join(PROJECT_ROOT, "Memory", "chat_archive.db")

TRANSIENT_KEYS = [
    "active_skills",
    "skills_index",
    "user_profile",
    "relevant_memories",
    "fast_path_matched",
    "next_node",
    "error_logs"
]

def save_interrupted_task_checkpoint(state_values: Dict[str, Any], status: str = "running") -> None:
    """Atomically serializes active execution state to prevent data loss on unexpected shutdown."""
    try:
        working_memory = state_values.get("working_memory", {}) or {}
        filtered_wm = {k: v for k, v in working_memory.items() if k not in TRANSIENT_KEYS}

        data = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "primary_goal": state_values.get("primary_goal", ""),
            "active_subtasks": state_values.get("active_subtasks", []),
            "working_memory": filtered_wm,
            "completed_tasks": state_values.get("completed_tasks", {}),
            "chat_history": state_values.get("chat_history", [])
        }

        os.makedirs(os.path.dirname(INTERRUPTED_TASK_PATH), exist_ok=True)
        tmp_path = f"{INTERRUPTED_TASK_PATH}.{threading.get_ident()}_{os.getpid()}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Atomic rename to prevent corrupt files on abrupt process death
        os.replace(tmp_path, INTERRUPTED_TASK_PATH)
    except Exception as e:
        print(f"⚠️ [SessionManager] Failed to save interrupted task checkpoint: {e}", flush=True)

def clear_interrupted_task_checkpoint() -> None:
    """Removes interrupted checkpoint upon clean completion."""
    try:
        if os.path.exists(INTERRUPTED_TASK_PATH):
            os.remove(INTERRUPTED_TASK_PATH)
    except Exception as e:
        print(f"⚠️ [SessionManager] Failed to clear interrupted task checkpoint: {e}", flush=True)

def get_interrupted_task() -> Optional[Dict[str, Any]]:
    """Loads interrupted task checkpoint if present."""
    if os.path.exists(INTERRUPTED_TASK_PATH):
        try:
            with open(INTERRUPTED_TASK_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def archive_chat_turn(session_id: str, role: str, content: str) -> None:
    """Archives conversational messages into SQLite FTS5 table."""
    try:
        os.makedirs(os.path.dirname(CHAT_ARCHIVE_PATH), exist_ok=True)
        with sqlite3.connect(CHAT_ARCHIVE_PATH, timeout=10.0) as conn:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chat_history_fts USING fts5(
                    session_id,
                    timestamp,
                    role,
                    content
                )
            """)
            conn.execute(
                "INSERT INTO chat_history_fts (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                (session_id, datetime.now().isoformat(), role, content)
            )
            conn.commit()
    except Exception as e:
        print(f"⚠️ [SessionManager] Chat archive error: {e}")

def save_session_context(
    chat_history: List[Dict[str, str]],
    working_memory: Dict[str, Any],
    completed_tasks: Dict[str, Any],
    session_summary: str = "",
    session_id: str = "default"
) -> None:
    """Persists conversational session context for resumption after closing."""
    try:
        filtered_wm = {k: v for k, v in (working_memory or {}).items() if k not in TRANSIENT_KEYS}
        context_data = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "chat_history": chat_history or [],
            "working_memory": filtered_wm,
            "completed_tasks": completed_tasks or {},
            "session_summary": session_summary or working_memory.get("session_summary", "")
        }

        os.makedirs(os.path.dirname(SESSION_CONTEXT_PATH), exist_ok=True)
        tmp_path = f"{SESSION_CONTEXT_PATH}.{threading.get_ident()}_{os.getpid()}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(context_data, f, indent=2)
        os.replace(tmp_path, SESSION_CONTEXT_PATH)

        # Archive last turn
        if chat_history and len(chat_history) >= 2:
            last_user = chat_history[-2]
            last_assistant = chat_history[-1]
            if last_user.get("role") == "user" and last_assistant.get("role") == "assistant":
                archive_chat_turn(session_id, "user", last_user.get("content", ""))
                archive_chat_turn(session_id, "assistant", last_assistant.get("content", ""))
    except Exception as e:
        print(f"⚠️ [SessionManager] Failed to save session context: {e}", flush=True)

def save_session_context_async(
    chat_history: List[Dict[str, str]],
    working_memory: Dict[str, Any],
    completed_tasks: Dict[str, Any],
    session_summary: str = "",
    session_id: str = "default"
) -> threading.Thread:
    """Asynchronously persists session context in the background."""
    thread = threading.Thread(
        target=save_session_context,
        args=(chat_history, working_memory, completed_tasks, session_summary, session_id),
        daemon=True
    )
    thread.start()
    return thread

def load_session_context() -> Optional[Dict[str, Any]]:
    """Loads persisted session context if present."""
    if os.path.exists(SESSION_CONTEXT_PATH):
        try:
            with open(SESSION_CONTEXT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def clear_session_context() -> None:
    """Clears persisted session context."""
    try:
        if os.path.exists(SESSION_CONTEXT_PATH):
            os.remove(SESSION_CONTEXT_PATH)
    except Exception as e:
        print(f"⚠️ [SessionManager] Failed to clear session context: {e}", flush=True)

import os
import re
import time
import threading
import contextvars
import uuid
from typing import Dict, Any, Optional, List

from .Engines.base_engine import BaseMemoryEngine
from .Engines.sqlite_engine import SQLiteMemoryEngine
from .Engines.postgres_engine import PostgresMemoryEngine

# Context variable to hold transaction ID for thread-local and async task-local isolation
_current_transaction = contextvars.ContextVar("current_transaction", default=None)

# Context variable to track the currently executing worker in the thread/task context
_current_worker = contextvars.ContextVar("current_worker", default=None)

# Regex patterns for custom XML tags in worker outputs
ENTITY_PATTERNS = {
    "urls": [r"<url>(.*?)</url>"],
    "emails": [r"<email>(.*?)</email>"],
    "passwords": [r"<pass>(.*?)</pass>", r"<password>(.*?)</password>"],
    "code_snippets": [r"<code_snippet>(.*?)</code_snippet>", r"<code>(.*?)</code>"],
    "shared_data": [r"<share>(.*?)</share>", r"<cache>(.*?)</cache>"],
}
GENERIC_ENTITY_PATTERN = r'<entity\s+type=["\'](.*?)["\']>(.*?)</entity>'


# ==========================================
# UNIFIED MEMORY WRAPPER (MemoryManager)
# ==========================================
class MemoryManager:
    """The central manager exposing the thread-safe API to the rest of the application."""

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(MemoryManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: str = "Memory/workspace_cache.db"):
        if getattr(self, "_initialized", False):
            return

        self.db_path = db_path
        self.enabled = os.environ.get("ENABLE_UNIFIED_MEMORY", "true").lower() == "true"
        self.engine = None
        if self.enabled:
            self.engine = self._initialize_engine()
        else:
            print("ℹ️ [MemoryManager] Unified Memory is disabled in environment settings.")
        self._thread_buffers = {}
        self._buffer_lock = threading.Lock()
        self._initialized = True

    def _initialize_engine(self) -> BaseMemoryEngine:
        db_provider = os.environ.get("DATABASE_PROVIDER", "").lower()
        db_url = os.environ.get("DATABASE_URL")
        
        if db_provider == "postgres" and db_url:
            try:
                engine = PostgresMemoryEngine(db_url)
                print("⚡ [MemoryManager] Connected successfully to Postgres database.")
                return engine
            except Exception as e:
                print(f"⚠️ [MemoryManager] Postgres connection failed ({e}). Falling back to SQLite.")

        print(f"📁 [MemoryManager] Initialized local SQLite cache backend at '{self.db_path}'")
        return SQLiteMemoryEngine(db_path=self.db_path)

    # --- TAG EXTRACTION HELPERS ---
    @staticmethod
    def extract_entities(text: str) -> Dict[str, Any]:
        """Parses custom tags and returns a dictionary of extracted entities and clean summary text."""
        if not isinstance(text, str):
            return {"summary": text, "extracted_entities": {}}

        extracted = {k: [] for k in ENTITY_PATTERNS.keys()}

        # 1. Parse tag-specific entities
        for category, patterns in ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, flags=re.DOTALL)
                for match in matches:
                    val = match.strip()
                    if val and val not in extracted[category]:
                        extracted[category].append(val)

        # 2. Parse generic `<entity type="xxx">` entities
        generic_matches = re.findall(GENERIC_ENTITY_PATTERN, text, flags=re.DOTALL)
        for entity_type, val_content in generic_matches:
            category = f"{entity_type.strip().lower()}s"
            val = val_content.strip()
            if val:
                if category not in extracted:
                    extracted[category] = []
                if val not in extracted[category]:
                    extracted[category].append(val)

        # 3. Clean up the tags from summary text but preserve their values inline
        clean_text = text
        for patterns in ENTITY_PATTERNS.values():
            for pattern in patterns:
                # Replace tags e.g. <url>http://abc</url> -> http://abc
                clean_text = re.sub(pattern.replace("(.*?)", "(.*?)"), r"\1", clean_text, flags=re.DOTALL)

        # Replace generic entity tags e.g. <entity type="url">abc</entity> -> abc
        clean_text = re.sub(GENERIC_ENTITY_PATTERN, r"\2", clean_text, flags=re.DOTALL)

        return {
            "summary": clean_text.strip(),
            "extracted_entities": {k: v for k, v in extracted.items() if v},
        }

    @staticmethod
    def get_current_worker() -> Optional[str]:
        """Gets the active worker name from the execution context."""
        return _current_worker.get()

    @staticmethod
    def set_current_worker(worker_name: Optional[str]):
        """Sets the active worker name in the execution context and returns the token to reset it."""
        return _current_worker.set(worker_name)

    @staticmethod
    def reset_current_worker(token) -> None:
        """Resets the active worker name in the execution context using the token."""
        try:
            _current_worker.reset(token)
        except Exception:
            pass

    # --- CORE APIs ---
    def init_transaction(self, txn_id: str) -> None:
        """Initializes a local buffer for the specified transaction ID."""
        if not self.enabled:
            return
        with self._buffer_lock:
            self._thread_buffers[txn_id] = {}

    def _commit_transaction_by_id(self, txn_id: str) -> None:
        """Commits all stored memory items from the transaction buffer to the main database engine."""
        if not self.enabled:
            return
        with self._buffer_lock:
            buffer = self._thread_buffers.pop(txn_id, None)
        if buffer:
            for key, item in buffer.items():
                data, sharable, persistent, ttl_seconds = item
                self._store_to_engine(key, data, sharable, persistent, ttl_seconds)

    def _discard_transaction_by_id(self, txn_id: str) -> None:
        """Discards all stored memory items in the transaction buffer."""
        if not self.enabled:
            return
        with self._buffer_lock:
            self._thread_buffers.pop(txn_id, None)

    def start_transaction(self) -> tuple:
        """Starts a transaction context and returns the txn_id and reset token."""
        if not self.enabled:
            return "dummy_txn", None
        txn_id = uuid.uuid4().hex
        token = _current_transaction.set(txn_id)
        self.init_transaction(txn_id)
        return txn_id, token

    def commit_transaction(self, txn_id: str, token) -> None:
        """Commits the active transaction and resets context variable."""
        if not self.enabled:
            return
        self._commit_transaction_by_id(txn_id)
        try:
            _current_transaction.reset(token)
        except Exception:
            pass

    def discard_transaction(self, txn_id: str, token) -> None:
        """Discards the active transaction and resets context variable."""
        if not self.enabled:
            return
        self._discard_transaction_by_id(txn_id)
        try:
            _current_transaction.reset(token)
        except Exception:
            pass

    def store_memory(self, key: str, data: Any, sharable: bool = False, persistent: bool = False, ttl_seconds: int = 1800) -> None:
        """Stores a memory payload, routing to the transaction buffer if active, otherwise directly to the database."""
        if not self.enabled:
            return
        txn_id = _current_transaction.get()
        in_buffer = False
        if txn_id is not None:
            with self._buffer_lock:
                in_buffer = txn_id in self._thread_buffers

        if in_buffer:
            with self._buffer_lock:
                self._thread_buffers[txn_id][key] = (data, sharable, persistent, ttl_seconds)
            return

        self._store_to_engine(key, data, sharable, persistent, ttl_seconds)

    def _store_to_engine(self, key: str, data: Any, sharable: bool = False, persistent: bool = False, ttl_seconds: int = 1800) -> None:
        """Helper that does the actual work of storing payload to the engine database."""
        if not self.enabled:
            return
            
        if persistent:
            ttl_seconds = 315360000  # 10 years

        payload = {
            "timestamp": time.time(),
            "sharable": "yes" if sharable else "no",
            "persistent": "yes" if persistent else "no",
        }

        if isinstance(data, str):
            parsed = self.extract_entities(data)
            payload["summary"] = parsed["summary"]
            payload["extracted_entities"] = parsed["extracted_entities"]
        elif isinstance(data, dict):
            payload["summary"] = data.get("summary", "")
            payload["extracted_entities"] = data.get("extracted_entities", {})
            for k, v in data.items():
                if k not in ["timestamp", "sharable", "persistent", "summary", "extracted_entities"]:
                    payload[k] = v
        else:
            payload["summary"] = str(data)
            payload["extracted_entities"] = {}

        self.engine.set(key, payload, ttl_seconds=ttl_seconds)

    def retrieve_memory(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieves a memory payload dictionary by key from the transaction buffer first, then falling back to the engine."""
        if not self.enabled:
            return None
        txn_id = _current_transaction.get()
        in_buffer = False
        if txn_id is not None:
            with self._buffer_lock:
                in_buffer = txn_id in self._thread_buffers and key in self._thread_buffers[txn_id]

        if in_buffer:
            with self._buffer_lock:
                data, sharable, persistent, ttl_seconds = self._thread_buffers[txn_id][key]
            # Construct mock payload for read-own-write consistency
            payload = {
                "timestamp": time.time(),
                "sharable": "yes" if sharable else "no",
                "persistent": "yes" if persistent else "no",
            }
            if isinstance(data, str):
                parsed = self.extract_entities(data)
                payload["summary"] = parsed["summary"]
                payload["extracted_entities"] = parsed["extracted_entities"]
            elif isinstance(data, dict):
                payload["summary"] = data.get("summary", "")
                payload["extracted_entities"] = data.get("extracted_entities", {})
                for k, v in data.items():
                    if k not in ["timestamp", "sharable", "persistent", "summary", "extracted_entities"]:
                        payload[k] = v
            else:
                payload["summary"] = str(data)
                payload["extracted_entities"] = {}
            return payload

        return self.engine.get(key)

    def delete_memory(self, key: str) -> None:
        """Deletes a key from the cache."""
        if not self.enabled:
            return
        txn_id = _current_transaction.get()
        in_buffer = False
        if txn_id is not None:
            with self._buffer_lock:
                in_buffer = txn_id in self._thread_buffers and key in self._thread_buffers[txn_id]

        if in_buffer:
            with self._buffer_lock:
                del self._thread_buffers[txn_id][key]
            return
        self.engine.delete(key)

    def list_keys(self, pattern: str = "*") -> List[str]:
        """Lists active keys matching pattern."""
        if not self.enabled:
            return []
        return self.engine.keys(pattern)

    def acquire_lock(self, lock_name: str, lease_time: int = 5) -> bool:
        """Acquires a lock with lease timeout."""
        if not self.enabled:
            return True
        return self.engine.acquire_lock(lock_name, lease_time)

    def release_lock(self, lock_name: str) -> None:
        """Releases lock."""
        if not self.enabled:
            return
        self.engine.release_lock(lock_name)

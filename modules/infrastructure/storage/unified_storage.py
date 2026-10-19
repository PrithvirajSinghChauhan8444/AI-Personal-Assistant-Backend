import os
import json
import sqlite3
import threading
from typing import Dict, Any, Optional, List

class UnifiedStorage:
    """Thread-safe transactional key-value cache engine backed by SQLite."""
    _instances: Dict[str, "UnifiedStorage"] = {}
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None):
        if not db_path:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            db_path = os.path.join(project_root, "Memory", "workspace_cache.db")
        db_path = os.path.abspath(db_path)

        with cls._lock:
            if db_path not in cls._instances:
                instance = super(UnifiedStorage, cls).__new__(cls)
                instance._init_db(db_path)
                cls._instances[db_path] = instance
            return cls._instances[db_path]

    def _init_db(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._local = threading.local()
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=30.0)
        return self._local.conn

    def set(self, key: str, value: Any) -> None:
        try:
            from modules.infrastructure.observability.telemetry import get_module_tracer
            tracer = get_module_tracer("storage")
        except Exception:
            tracer = None

        if tracer:
            with tracer.start_as_current_span("storage.set") as span:
                span.set_attribute("db.system", "sqlite")
                span.set_attribute("db.operation", "set")
                span.set_attribute("db.key", key)
                val_str = json.dumps(value)
                conn = self._get_conn()
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", (key, val_str))
                conn.commit()
        else:
            val_str = json.dumps(value)
            conn = self._get_conn()
            conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", (key, val_str))
            conn.commit()

    def get(self, key: str) -> Optional[Any]:
        try:
            from modules.infrastructure.observability.telemetry import get_module_tracer
            tracer = get_module_tracer("storage")
        except Exception:
            tracer = None

        if tracer:
            with tracer.start_as_current_span("storage.get") as span:
                span.set_attribute("db.system", "sqlite")
                span.set_attribute("db.operation", "get")
                span.set_attribute("db.key", key)
                conn = self._get_conn()
                cursor = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
                row = cursor.fetchone()
                hit = row is not None
                span.set_attribute("db.cache_hit", hit)
                if hit:
                    return json.loads(row[0])
                return None
        else:
            conn = self._get_conn()
            cursor = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def delete(self, key: str) -> None:
        try:
            from modules.infrastructure.observability.telemetry import get_module_tracer
            tracer = get_module_tracer("storage")
        except Exception:
            tracer = None

        if tracer:
            with tracer.start_as_current_span("storage.delete") as span:
                span.set_attribute("db.system", "sqlite")
                span.set_attribute("db.operation", "delete")
                span.set_attribute("db.key", key)
                conn = self._get_conn()
                conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
                conn.commit()
        else:
            conn = self._get_conn()
            conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
            conn.commit()


    def list_keys(self, prefix: str = "") -> List[str]:
        conn = self._get_conn()
        cursor = conn.execute("SELECT key FROM kv_store WHERE key LIKE ?", (f"{prefix}%",))
        return [row[0] for row in cursor.fetchall()]

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

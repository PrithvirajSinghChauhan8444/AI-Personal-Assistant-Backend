import os
import json
import time
import sqlite3
import threading
from typing import List, Dict, Any, Optional

from .base_engine import BaseMemoryEngine

class SQLiteMemoryEngine(BaseMemoryEngine):
    """SQLite implementation of the memory engine, supporting thread-safe operation and lazy TTL."""

    def __init__(self, db_path: str = "Memory/workspace_cache.db"):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        # Enable write-ahead logging (WAL) for better concurrent performance
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                # Main cache table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        expires_at REAL
                    )
                """
                )
                # Lock table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS locks (
                        lock_name TEXT PRIMARY KEY,
                        expires_at REAL
                    )
                """
                )
                conn.commit()
            finally:
                conn.close()

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 1800) -> None:
        expires_at = time.time() + ttl_seconds
        val_str = json.dumps(value)
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                    (key, val_str, expires_at),
                )
                conn.commit()
            finally:
                conn.close()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            conn = self._get_connection()
            try:
                # Lazy TTL clean-up on read
                conn.execute("DELETE FROM cache WHERE key = ? AND expires_at < ?", (key, now))
                conn.commit()

                cursor = conn.execute("SELECT value FROM cache WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
            finally:
                conn.close()
        return None

    def delete(self, key: str) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()

    def keys(self, pattern: str) -> List[str]:
        # Simple SQL translation for keys search
        sql_pattern = pattern.replace("*", "%").replace("?", "_")
        now = time.time()
        with self._lock:
            conn = self._get_connection()
            try:
                # Filter expired keys out
                cursor = conn.execute(
                    "SELECT key FROM cache WHERE key LIKE ? AND expires_at >= ?",
                    (sql_pattern, now),
                )
                return [row[0] for row in cursor.fetchall()]
            finally:
                conn.close()

    def acquire_lock(self, lock_name: str, lease_time: int = 5) -> bool:
        now = time.time()
        expires_at = now + lease_time
        with self._lock:
            conn = self._get_connection()
            try:
                # 1. Delete expired lock if any
                conn.execute("DELETE FROM locks WHERE lock_name = ? AND expires_at < ?", (lock_name, now))
                conn.commit()

                # 2. Try to insert lock
                conn.execute("INSERT INTO locks (lock_name, expires_at) VALUES (?, ?)", (lock_name, expires_at))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Lock is already held and not expired
                return False
            finally:
                conn.close()

    def release_lock(self, lock_name: str) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("DELETE FROM locks WHERE lock_name = ?", (lock_name,))
                conn.commit()
            finally:
                conn.close()

import json
import time
from typing import List, Dict, Any, Optional

from .base_engine import BaseMemoryEngine

class PostgresMemoryEngine(BaseMemoryEngine):
    """Postgres implementation of the memory engine, supporting hybrid/relational storage and thread-safety."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._init_db()

    def _get_connection(self):
        import psycopg2
        return psycopg2.connect(self.database_url)

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Cache table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        value JSONB,
                        expires_at DOUBLE PRECISION
                    )
                    """
                )
                # Lock table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS locks (
                        lock_name TEXT PRIMARY KEY,
                        expires_at DOUBLE PRECISION
                    )
                    """
                )
                conn.commit()
        finally:
            conn.close()

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 1800) -> None:
        expires_at = time.time() + ttl_seconds
        val_str = json.dumps(value)
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache (key, value, expires_at) VALUES (%s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at
                    """,
                    (key, val_str, expires_at),
                )
                conn.commit()
        finally:
            conn.close()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Lazy TTL clean-up on read
                cur.execute("DELETE FROM cache WHERE key = %s AND expires_at < %s", (key, now))
                conn.commit()

                cur.execute("SELECT value FROM cache WHERE key = %s", (key,))
                row = cur.fetchone()
                if row:
                    val = row[0]
                    if isinstance(val, str):
                        return json.loads(val)
                    return val
        finally:
            conn.close()
        return None

    def delete(self, key: str) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cache WHERE key = %s", (key,))
                conn.commit()
        finally:
            conn.close()

    def keys(self, pattern: str) -> List[str]:
        # Translate glob pattern to SQL LIKE pattern
        sql_pattern = pattern.replace("*", "%").replace("?", "_")
        now = time.time()
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key FROM cache WHERE key LIKE %s AND expires_at >= %s",
                    (sql_pattern, now),
                )
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def acquire_lock(self, lock_name: str, lease_time: int = 5) -> bool:
        import psycopg2
        now = time.time()
        expires_at = now + lease_time
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 1. Delete expired lock if any
                cur.execute("DELETE FROM locks WHERE lock_name = %s AND expires_at < %s", (lock_name, now))
                conn.commit()

                # 2. Try to insert lock
                cur.execute("INSERT INTO locks (lock_name, expires_at) VALUES (%s, %s)", (lock_name, expires_at))
                conn.commit()
                return True
        except psycopg2.IntegrityError:
            return False
        finally:
            conn.close()

    def release_lock(self, lock_name: str) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM locks WHERE lock_name = %s", (lock_name,))
                conn.commit()
        finally:
            conn.close()

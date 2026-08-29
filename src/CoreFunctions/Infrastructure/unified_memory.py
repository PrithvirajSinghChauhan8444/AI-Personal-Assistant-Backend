import os
import re
import json
import time
import sqlite3
import threading
import contextvars
import uuid
from typing import List, Dict, Any, Optional

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
# 1. BASE ENGINE INTERFACE
# ==========================================
class BaseMemoryEngine:
    """Abstract Base Class defining the standard interface for all memory cache backends."""

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 1800) -> None:
        raise NotImplementedError

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def keys(self, pattern: str) -> List[str]:
        raise NotImplementedError

    def acquire_lock(self, lock_name: str, lease_time: int = 5) -> bool:
        raise NotImplementedError

    def release_lock(self, lock_name: str) -> None:
        raise NotImplementedError

    def add_relation(self, source: str, relation: str, target: str, context: str = "") -> None:
        raise NotImplementedError

    def query_relations(self, source: str = None, relation: str = None, target: str = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def delete_relation(self, source: str, relation: str, target: str) -> None:
        raise NotImplementedError

    def upsert_person(self, name: str, relation: str = "", email: str = "", phone: str = "", notes: str = "") -> None:
        pass

    def query_people(self, name: str = None, relation: str = None) -> List[Dict[str, Any]]:
        return []

    def upsert_profile(self, key: str, value: str, source: str) -> None:
        pass

    def query_profile(self, key: str = None) -> List[Dict[str, Any]]:
        return []

    def add_to_profile_review(self, key: str, value: str, source: str) -> None:
        pass

    def query_profile_review(self) -> List[Dict[str, Any]]:
        return []

    def delete_from_profile_review(self, review_id: int) -> None:
        pass

    def log_event(self, event_type: str, summary: str, ref_id: str = "", timestamp: float = None) -> None:
        pass

    def query_events(self, event_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    def upsert_vector_fact(self, fact: str, source: str, timestamp: float = None, access_count: int = 1) -> None:
        pass

    def delete_vector_fact(self, fact: str) -> None:
        pass

    def list_vector_facts(self) -> List[Dict[str, Any]]:
        return []


# ==========================================
# 2. SQLITE CACHE ENGINE (Zero Setup fallback)
# ==========================================
class SQLiteMemoryEngine(BaseMemoryEngine):
    """SQLite implementation of the memory engine, sharded by worker/domain with isolated locks."""

    def __init__(self, db_path: str = "Memory/workspace_cache.db"):
        self.db_path = os.path.abspath(db_path)
        self.shards_dir = os.path.join(os.path.dirname(self.db_path), "shards")
        os.makedirs(self.shards_dir, exist_ok=True)
        self._locks = {}
        self._locks_mutex = threading.Lock()
        
        # Initialize default database
        default_lock = threading.Lock()
        self._locks[self.db_path] = default_lock
        self._init_db_path(self.db_path, default_lock)

    def _init_db_path(self, db_path: str, lock: threading.Lock) -> None:
        with lock:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
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
                # Graph relations table (stored in the main shard workspace_cache.db)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS relations (
                        source_entity TEXT,
                        relation TEXT,
                        target_entity TEXT,
                        timestamp REAL,
                        context TEXT,
                        PRIMARY KEY (source_entity, relation, target_entity)
                    )
                """
                )
                # People table (CRM)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS people (
                        name TEXT PRIMARY KEY,
                        relation TEXT,
                        email TEXT,
                        phone TEXT,
                        notes TEXT
                    )
                """
                )
                # Profile table (structured canonical profile)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS profile (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        source TEXT,
                        timestamp REAL
                    )
                """
                )
                # Review queue table for unrecognized fields
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS profile_review_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT,
                        value TEXT,
                        source TEXT,
                        timestamp REAL
                    )
                """
                )
                # Events table (timeline logs)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        event_type TEXT,
                        summary TEXT,
                        ref_id TEXT
                    )
                """
                )
                # Vector facts table (SQL Source of Truth for FAISS)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS vector_facts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fact TEXT UNIQUE,
                        source TEXT,
                        timestamp REAL,
                        access_count INTEGER DEFAULT 1
                    )
                """
                )
                conn.commit()
            finally:
                conn.close()

    def _get_shard_path_and_lock(self, key_or_pattern: str) -> tuple:
        db_path = self.db_path
        # Parse worker name if it follows the format worker:worker_name:...
        match = re.match(r"^worker:([^:*?%]+)", key_or_pattern)
        if match:
            worker_name = match.group(1)
            db_path = os.path.join(self.shards_dir, f"worker_{worker_name}.db")
        
        with self._locks_mutex:
            if db_path not in self._locks:
                lock = threading.Lock()
                self._locks[db_path] = lock
                self._init_db_path(db_path, lock)
            else:
                lock = self._locks[db_path]
        return db_path, lock

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 1800) -> None:
        db_path, lock = self._get_shard_path_and_lock(key)
        expires_at = time.time() + ttl_seconds
        val_str = json.dumps(value)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                    (key, val_str, expires_at),
                )
                conn.commit()
            finally:
                conn.close()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        db_path, lock = self._get_shard_path_and_lock(key)
        now = time.time()
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
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
        db_path, lock = self._get_shard_path_and_lock(key)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()

    def _keys_in_db(self, db_path: str, lock: threading.Lock, pattern: str) -> List[str]:
        sql_pattern = pattern.replace("*", "%").replace("?", "_")
        now = time.time()
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute("DELETE FROM cache WHERE key LIKE ? AND expires_at < ?", (sql_pattern, now))
                conn.commit()

                cursor = conn.execute(
                    "SELECT key FROM cache WHERE key LIKE ? AND expires_at >= ?",
                    (sql_pattern, now),
                )
                return [row[0] for row in cursor.fetchall()]
            finally:
                conn.close()

    def keys(self, pattern: str) -> List[str]:
        # If pattern is specific to a worker name, only search that shard
        match = re.match(r"^worker:([^:*?%]+)", pattern)
        if match:
            db_path, lock = self._get_shard_path_and_lock(pattern)
            return self._keys_in_db(db_path, lock, pattern)

        # Broad search across all active shards
        all_keys = []
        shards = [self.db_path]
        if os.path.exists(self.shards_dir):
            for f in os.listdir(self.shards_dir):
                if f.endswith(".db"):
                    shards.append(os.path.join(self.shards_dir, f))

        for db_path in shards:
            with self._locks_mutex:
                if db_path not in self._locks:
                    self._locks[db_path] = threading.Lock()
                lock = self._locks[db_path]
            all_keys.extend(self._keys_in_db(db_path, lock, pattern))
        return all_keys

    def acquire_lock(self, lock_name: str, lease_time: int = 5) -> bool:
        db_path, lock = self._get_shard_path_and_lock(lock_name)
        now = time.time()
        expires_at = now + lease_time
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
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
        db_path, lock = self._get_shard_path_and_lock(lock_name)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute("DELETE FROM locks WHERE lock_name = ?", (lock_name,))
                conn.commit()
            finally:
                conn.close()

    def add_relation(self, source: str, relation: str, target: str, context: str = "") -> None:
        db_path, lock = self._get_shard_path_and_lock("relations")
        now = time.time()
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO relations (source_entity, relation, target_entity, timestamp, context) VALUES (?, ?, ?, ?, ?)",
                    (source.strip().lower(), relation.strip().lower(), target.strip().lower(), now, context),
                )
                conn.commit()
            finally:
                conn.close()

    def query_relations(self, source: str = None, relation: str = None, target: str = None) -> List[Dict[str, Any]]:
        db_path, lock = self._get_shard_path_and_lock("relations")
        query = "SELECT source_entity, relation, target_entity, timestamp, context FROM relations WHERE 1=1"
        params = []
        if source:
            query += " AND source_entity = ?"
            params.append(source.strip().lower())
        if relation:
            query += " AND relation = ?"
            params.append(relation.strip().lower())
        if target:
            query += " AND target_entity = ?"
            params.append(target.strip().lower())
            
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.execute(query, params)
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "source": row[0],
                        "relation": row[1],
                        "target": row[2],
                        "timestamp": row[3],
                        "context": row[4]
                    })
                return results
            finally:
                conn.close()

    def delete_relation(self, source: str, relation: str, target: str) -> None:
        db_path, lock = self._get_shard_path_and_lock("relations")
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute(
                    "DELETE FROM relations WHERE source_entity = ? AND relation = ? AND target_entity = ?",
                    (source.strip().lower(), relation.strip().lower(), target.strip().lower()),
                )
                conn.commit()
            finally:
                conn.close()

    def upsert_person(self, name: str, relation: str = "", email: str = "", phone: str = "", notes: str = "") -> None:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO people (name, relation, email, phone, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        name.strip() if name else "", 
                        relation.strip() if relation else "", 
                        email.strip() if email else "", 
                        phone.strip() if phone else "", 
                        notes.strip() if notes else ""
                    )
                )
                conn.commit()
            finally:
                conn.close()

    def query_people(self, name: str = None, relation: str = None) -> List[Dict[str, Any]]:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        query = "SELECT name, relation, email, phone, notes FROM people WHERE 1=1"
        params = []
        if name:
            query += " AND name = ?"
            params.append(name.strip())
        if relation:
            query += " AND relation = ?"
            params.append(relation.strip())
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.execute(query, params)
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "name": row[0],
                        "relation": row[1],
                        "email": row[2],
                        "phone": row[3],
                        "notes": row[4]
                    })
                return results
            finally:
                conn.close()

    def upsert_profile(self, key: str, value: str, source: str) -> None:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        now = time.time()
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO profile (key, value, source, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        key.strip().lower() if key else "", 
                        value.strip() if value else "", 
                        source.strip() if source else "", 
                        now
                    )
                )
                conn.commit()
            finally:
                conn.close()

    def query_profile(self, key: str = None) -> List[Dict[str, Any]]:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        query = "SELECT key, value, source, timestamp FROM profile"
        params = []
        if key:
            query += " WHERE key = ?"
            params.append(key.strip().lower())
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.execute(query, params)
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "key": row[0],
                        "value": row[1],
                        "source": row[2],
                        "timestamp": row[3]
                    })
                return results
            finally:
                conn.close()

    def add_to_profile_review(self, key: str, value: str, source: str) -> None:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        now = time.time()
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute(
                    """
                    INSERT INTO profile_review_queue (key, value, source, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        key.strip() if key else "", 
                        value.strip() if value else "", 
                        source.strip() if source else "", 
                        now
                    )
                )
                conn.commit()
            finally:
                conn.close()

    def query_profile_review(self) -> List[Dict[str, Any]]:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.execute("SELECT id, key, value, source, timestamp FROM profile_review_queue ORDER BY timestamp ASC")
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row[0],
                        "key": row[1],
                        "value": row[2],
                        "source": row[3],
                        "timestamp": row[4]
                    })
                return results
            finally:
                conn.close()

    def delete_from_profile_review(self, review_id: int) -> None:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute("DELETE FROM profile_review_queue WHERE id = ?", (review_id,))
                conn.commit()
            finally:
                conn.close()

    def log_event(self, event_type: str, summary: str, ref_id: str = "", timestamp: float = None) -> None:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        now = timestamp if timestamp is not None else time.time()
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute(
                    "INSERT INTO events (timestamp, event_type, summary, ref_id) VALUES (?, ?, ?, ?)",
                    (
                        now, 
                        event_type.strip() if event_type else "", 
                        summary.strip() if summary else "", 
                        ref_id.strip() if ref_id else ""
                    )
                )
                conn.commit()
            finally:
                conn.close()

    def query_events(self, event_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        query = "SELECT id, timestamp, event_type, summary, ref_id FROM events"
        params = []
        if event_type:
            query += " WHERE event_type = ?"
            params.append(event_type.strip())
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.execute(query, params)
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row[0],
                        "timestamp": row[1],
                        "event_type": row[2],
                        "summary": row[3],
                        "ref_id": row[4]
                    })
                return results
            finally:
                conn.close()

    def upsert_vector_fact(self, fact: str, source: str, timestamp: float = None, access_count: int = 1) -> None:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        now = timestamp if timestamp is not None else time.time()
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO vector_facts (fact, source, timestamp, access_count)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        fact.strip() if fact else "", 
                        source.strip() if source else "", 
                        now, 
                        access_count
                    )
                )
                conn.commit()
            finally:
                conn.close()

    def delete_vector_fact(self, fact: str) -> None:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.execute("DELETE FROM vector_facts WHERE fact = ?", (fact.strip() if fact else "",))
                conn.commit()
            finally:
                conn.close()

    def list_vector_facts(self) -> List[Dict[str, Any]]:
        db_path, lock = self._get_shard_path_and_lock(self.db_path)
        with lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.execute("SELECT id, fact, source, timestamp, access_count FROM vector_facts")
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row[0],
                        "fact": row[1],
                        "source": row[2],
                        "timestamp": row[3],
                        "access_count": row[4]
                    })
                return results
            finally:
                conn.close()

# ==========================================
# 3. POSTGRES CACHE ENGINE (Enterprise Production)
# ==========================================
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
                # Relations table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS relations (
                        source_entity TEXT,
                        relation TEXT,
                        target_entity TEXT,
                        timestamp DOUBLE PRECISION,
                        context TEXT,
                        PRIMARY KEY (source_entity, relation, target_entity)
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

    def add_relation(self, source: str, relation: str, target: str, context: str = "") -> None:
        now = time.time()
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO relations (source_entity, relation, target_entity, timestamp, context) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source_entity, relation, target_entity) DO UPDATE SET timestamp = EXCLUDED.timestamp, context = EXCLUDED.context
                    """,
                    (source.strip().lower(), relation.strip().lower(), target.strip().lower(), now, context),
                )
                conn.commit()
        finally:
            conn.close()

    def query_relations(self, source: str = None, relation: str = None, target: str = None) -> List[Dict[str, Any]]:
        query = "SELECT source_entity, relation, target_entity, timestamp, context FROM relations WHERE 1=1"
        params = []
        if source:
            query += " AND source_entity = %s"
            params.append(source.strip().lower())
        if relation:
            query += " AND relation = %s"
            params.append(relation.strip().lower())
        if target:
            query += " AND target_entity = %s"
            params.append(target.strip().lower())
            
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = []
                for row in cur.fetchall():
                    results.append({
                        "source": row[0],
                        "relation": row[1],
                        "target": row[2],
                        "timestamp": row[3],
                        "context": row[4]
                    })
                return results
        finally:
            conn.close()

    def delete_relation(self, source: str, relation: str, target: str) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM relations WHERE source_entity = %s AND relation = %s AND target_entity = %s",
                    (source.strip().lower(), relation.strip().lower(), target.strip().lower()),
                )
                conn.commit()
        finally:
            conn.close()


# ==========================================
# 4. REDIS CACHE ENGINE (High Performance Caching)
# ==========================================
class RedisMemoryEngine(BaseMemoryEngine):
    """Redis implementation of the memory engine using redis key TTL and distributed lock patterns."""

    def __init__(self, redis_url: str):
        import redis
        self.redis_url = redis_url
        self.client = redis.from_url(redis_url, decode_responses=True)
        # Ping connection to fail early if Redis is offline
        self.client.ping()

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 1800) -> None:
        val_str = json.dumps(value)
        self.client.set(key, val_str, ex=ttl_seconds)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        val_str = self.client.get(key)
        if val_str:
            return json.loads(val_str)
        return None

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def keys(self, pattern: str) -> List[str]:
        return self.client.keys(pattern)

    def acquire_lock(self, lock_name: str, lease_time: int = 5) -> bool:
        lock_key = f"lock:{lock_name}"
        success = self.client.set(lock_key, "1", nx=True, px=int(lease_time * 1000))
        return bool(success)

    def release_lock(self, lock_name: str) -> None:
        lock_key = f"lock:{lock_name}"
        self.client.delete(lock_key)

    def add_relation(self, source: str, relation: str, target: str, context: str = "") -> None:
        key = f"relation:{source.strip().lower()}:{relation.strip().lower()}:{target.strip().lower()}"
        payload = {
            "timestamp": time.time(),
            "context": context
        }
        self.client.set(key, json.dumps(payload))

    def query_relations(self, source: str = None, relation: str = None, target: str = None) -> List[Dict[str, Any]]:
        s_part = source.strip().lower() if source else "*"
        r_part = relation.strip().lower() if relation else "*"
        t_part = target.strip().lower() if target else "*"
        pattern = f"relation:{s_part}:{r_part}:{t_part}"
        keys = self.client.keys(pattern)
        
        results = []
        for key in keys:
            parts = key.split(":")
            if len(parts) == 4:
                val_str = self.client.get(key)
                if val_str:
                    payload = json.loads(val_str)
                    results.append({
                        "source": parts[1],
                        "relation": parts[2],
                        "target": parts[3],
                        "timestamp": payload.get("timestamp"),
                        "context": payload.get("context", "")
                    })
        return results

    def delete_relation(self, source: str, relation: str, target: str) -> None:
        key = f"relation:{source.strip().lower()}:{relation.strip().lower()}:{target.strip().lower()}"
        self.client.delete(key)


# ==========================================
# 5. UNIFIED MEMORY WRAPPER
# ==========================================
class UnifiedMemory:
    """The central manager exposing the thread-safe API to the rest of the application."""

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(UnifiedMemory, cls).__new__(cls)
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
            print("ℹ️ [UnifiedMemory] Unified Memory is disabled in environment settings.")
        self._thread_buffers = {}
        self._buffer_lock = threading.Lock()
        self._initialized = True

    def _initialize_engine(self) -> BaseMemoryEngine:
        db_provider = os.environ.get("DATABASE_PROVIDER", "").lower()
        db_url = os.environ.get("DATABASE_URL")
        redis_url = os.environ.get("REDIS_URL")
        
        if db_provider == "redis" or (not db_provider and redis_url):
            try:
                url_to_use = redis_url or db_url
                if url_to_use:
                    engine = RedisMemoryEngine(url_to_use)
                    print("⚡ [UnifiedMemory] Connected successfully to Redis server.")
                    return engine
            except Exception as e:
                print(f"⚠️ [UnifiedMemory] Redis connection failed ({e}). Falling back to SQLite.")

        if db_provider == "postgres" and db_url:
            try:
                engine = PostgresMemoryEngine(db_url)
                print("⚡ [UnifiedMemory] Connected successfully to Postgres database.")
                return engine
            except Exception as e:
                print(f"⚠️ [UnifiedMemory] Postgres connection failed ({e}). Falling back to SQLite.")

        print(f"📁 [UnifiedMemory] Initialized local SQLite cache backend at '{self.db_path}'")
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
        """Resets the active worker context using the provided token."""
        try:
            _current_worker.reset(token)
        except Exception:
            pass

    def run_maintenance(self) -> None:
        """Executes maintenance jobs, such as running VACUUM on SQLite shard databases."""
        if not self.enabled:
            return
        
        if isinstance(self.engine, SQLiteMemoryEngine):
            print("🔧 [UnifiedMemory] Running SQLite database maintenance (VACUUM)...")
            db_paths = [self.engine.db_path]
            if os.path.exists(self.engine.shards_dir):
                for f in os.listdir(self.engine.shards_dir):
                    if f.endswith(".db"):
                        db_paths.append(os.path.join(self.engine.shards_dir, f))
            
            for path in db_paths:
                with self.engine._locks_mutex:
                    if path not in self.engine._locks:
                        self.engine._locks[path] = threading.Lock()
                    lock = self.engine._locks[path]
                
                with lock:
                    try:
                        conn = sqlite3.connect(path, timeout=10.0)
                        conn.execute("VACUUM")
                        conn.commit()
                        print(f"   ✓ Vacuumed database: {os.path.basename(path)}")
                    except Exception as e:
                        print(f"   ⚠️ Vacuum failed for {os.path.basename(path)}: {e}")
                    finally:
                        conn.close()

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

    def add_relation(self, source: str, relation: str, target: str, context: str = "") -> None:
        """Adds a graph-shaped relation."""
        if not self.enabled:
            return
        self.engine.add_relation(source, relation, target, context)

    def query_relations(self, source: str = None, relation: str = None, target: str = None) -> List[Dict[str, Any]]:
        """Queries graph-shaped relations."""
        if not self.enabled:
            return []
        return self.engine.query_relations(source, relation, target)

    def delete_relation(self, source: str, relation: str, target: str) -> None:
        """Deletes a graph-shaped relation."""
        if not self.enabled:
            return
        self.engine.delete_relation(source, relation, target)

    def upsert_person(self, name: str, relation: str = "", email: str = "", phone: str = "", notes: str = "") -> None:
        if self.enabled:
            self.engine.upsert_person(name, relation, email, phone, notes)

    def query_people(self, name: str = None, relation: str = None) -> List[Dict[str, Any]]:
        if self.enabled:
            return self.engine.query_people(name, relation)
        return []

    def upsert_profile(self, key: str, value: str, source: str) -> None:
        if self.enabled:
            self.engine.upsert_profile(key, value, source)

    def query_profile(self, key: str = None) -> List[Dict[str, Any]]:
        if self.enabled:
            return self.engine.query_profile(key)
        return []

    def add_to_profile_review(self, key: str, value: str, source: str) -> None:
        if self.enabled:
            self.engine.add_to_profile_review(key, value, source)

    def query_profile_review(self) -> List[Dict[str, Any]]:
        if self.enabled:
            return self.engine.query_profile_review()
        return []

    def delete_from_profile_review(self, review_id: int) -> None:
        if self.enabled:
            self.engine.delete_from_profile_review(review_id)

    def log_event(self, event_type: str, summary: str, ref_id: str = "", timestamp: float = None) -> None:
        if self.enabled:
            self.engine.log_event(event_type, summary, ref_id, timestamp)

    def query_events(self, event_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        if self.enabled:
            return self.engine.query_events(event_type, limit)
        return []

    def upsert_vector_fact(self, fact: str, source: str, timestamp: float = None, access_count: int = 1) -> None:
        if self.enabled:
            self.engine.upsert_vector_fact(fact, source, timestamp, access_count)

    def delete_vector_fact(self, fact: str) -> None:
        if self.enabled:
            self.engine.delete_vector_fact(fact)

    def list_vector_facts(self) -> List[Dict[str, Any]]:
        if self.enabled:
            return self.engine.list_vector_facts()
        return []

"""SQLite Repository for Episodic Memory records, migrations, and audit trails."""

import json
import os
import sqlite3
import time
from typing import Dict, List, Optional, Tuple

from src.memory.contracts import EpisodicRecord


class EpisodicSqliteRepository:
    """Manages SQLite schema, persistence, audit trails, and queries for episodic memory."""

    def __init__(self, db_path: str) -> None:
        self.db_path = os.path.abspath(os.path.expanduser(db_path))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_sqlite()

    def get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection configured with WAL journal mode and busy timeout."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_sqlite(self) -> None:
        """Initializes episodic_memories schema with versioning and audit support."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    auto_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    source_session_id TEXT,
                    source_turn_id TEXT,
                    confidence REAL DEFAULT 1.0,
                    embedding_dim INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    supersedes TEXT,
                    version INTEGER DEFAULT 1,
                    deletion_reason TEXT
                );
            """)
            # Apply backward-compatible migrations
            for col_name, col_type in [
                ("is_active", "INTEGER DEFAULT 1"),
                ("supersedes", "TEXT"),
                ("version", "INTEGER DEFAULT 1"),
                ("deletion_reason", "TEXT"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE episodic_memories ADD COLUMN {col_name} {col_type};")
                except sqlite3.OperationalError:
                    pass

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_cat ON episodic_memories(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_time ON episodic_memories(created_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_active ON episodic_memories(is_active);")
            conn.commit()

    def find_exact_active_fact(self, content: str, category: str) -> Optional[Tuple[int, EpisodicRecord]]:
        """Checks if an identical active factual statement exists."""
        clean_content = content.strip().lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT auto_id, id, content, category, tags, source_session_id,
                       source_turn_id, confidence, embedding_dim, created_at, updated_at,
                       is_active, supersedes, version
                FROM episodic_memories
                WHERE LOWER(TRIM(content)) = ? AND category = ? AND is_active = 1
                LIMIT 1
                """,
                (clean_content, category),
            )
            row = cursor.fetchone()
            if not row:
                return None

            rec = EpisodicRecord(
                id=row[1],
                content=row[2],
                category=row[3],
                tags=json.loads(row[4] or "[]"),
                source_session_id=row[5],
                source_turn_id=row[6],
                confidence=row[7],
                embedding_dim=row[8],
                created_at=row[9],
                updated_at=row[10],
                is_active=bool(row[11]),
                supersedes=row[12],
                version=row[13] or 1,
            )
            return (row[0], rec)

    def update_tags(self, auto_id: int, tags: List[str], updated_at_ms: int) -> None:
        """Updates tags and timestamp for an existing memory record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE episodic_memories SET tags = ?, updated_at = ? WHERE auto_id = ?",
                (json.dumps(tags), updated_at_ms, auto_id),
            )
            conn.commit()

    def get_superseded_info(self, auto_id: int) -> Optional[Tuple[str, str, int]]:
        """Returns (id, category, version) for an active record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, category, version FROM episodic_memories WHERE auto_id = ? AND is_active = 1",
                (auto_id,),
            )
            row = cursor.fetchone()
            if row:
                return (row[0], row[1], row[2] or 1)
        return None

    def soft_delete(self, auto_id: int, reason: str, updated_at_ms: int) -> None:
        """Marks a record as inactive with an audit reason."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE episodic_memories SET is_active = 0, deletion_reason = ?, updated_at = ? WHERE auto_id = ?",
                (reason, updated_at_ms, auto_id),
            )
            conn.commit()

    def insert_record(
        self,
        mem_id: str,
        content: str,
        category: str,
        tags: List[str],
        source_session_id: Optional[str],
        source_turn_id: Optional[str],
        confidence: float,
        embedding_dim: int,
        supersedes_id: Optional[str],
        version: int,
        timestamp_ms: int,
    ) -> int:
        """Inserts a new active memory record and returns its SQLite auto_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO episodic_memories (
                    id, content, category, tags, source_session_id, source_turn_id,
                    confidence, embedding_dim, created_at, updated_at, is_active,
                    supersedes, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    mem_id,
                    content,
                    category,
                    json.dumps(tags),
                    source_session_id,
                    source_turn_id,
                    confidence,
                    embedding_dim,
                    timestamp_ms,
                    timestamp_ms,
                    supersedes_id,
                    version,
                ),
            )
            auto_id = cursor.lastrowid
            conn.commit()
            return auto_id

    def hydrate_records(self, auto_ids: List[int]) -> Dict[int, EpisodicRecord]:
        """Hydrates multiple active EpisodicRecord instances by auto_id."""
        if not auto_ids:
            return {}

        placeholders = ",".join("?" for _ in auto_ids)
        records: Dict[int, EpisodicRecord] = {}

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT auto_id, id, content, category, tags, source_session_id,
                       source_turn_id, confidence, embedding_dim, created_at, updated_at,
                       is_active, supersedes, version
                FROM episodic_memories
                WHERE auto_id IN ({placeholders}) AND is_active = 1
                """,
                auto_ids,
            )
            for row in cursor.fetchall():
                aid = row[0]
                records[aid] = EpisodicRecord(
                    id=row[1],
                    content=row[2],
                    category=row[3],
                    tags=json.loads(row[4] or "[]"),
                    source_session_id=row[5],
                    source_turn_id=row[6],
                    confidence=row[7],
                    embedding_dim=row[8],
                    created_at=row[9],
                    updated_at=row[10],
                    is_active=bool(row[11]),
                    supersedes=row[12],
                    version=row[13] or 1,
                )
        return records

    def get_by_id(self, memory_id: str) -> Optional[EpisodicRecord]:
        """Fetches a single active record by string id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, category, tags, source_session_id, source_turn_id,
                       confidence, embedding_dim, created_at, updated_at, is_active,
                       supersedes, version
                FROM episodic_memories
                WHERE id = ? AND is_active = 1
                """,
                (memory_id.strip(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return EpisodicRecord(
                id=row[0],
                content=row[1],
                category=row[2],
                tags=json.loads(row[3] or "[]"),
                source_session_id=row[4],
                source_turn_id=row[5],
                confidence=row[6],
                embedding_dim=row[7],
                created_at=row[8],
                updated_at=row[9],
                is_active=bool(row[10]),
                supersedes=row[11],
                version=row[12] or 1,
            )

    def find_auto_id_by_string_id(self, memory_id: str) -> Optional[int]:
        """Returns auto_id for an active memory string id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT auto_id FROM episodic_memories WHERE id = ? AND is_active = 1",
                (memory_id.strip(),),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_all_active_for_rebuild(self) -> List[Tuple[int, str]]:
        """Returns list of (auto_id, content) for all active records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT auto_id, content FROM episodic_memories WHERE is_active = 1 ORDER BY auto_id ASC"
            )
            return cursor.fetchall()

    def count_active(self) -> int:
        """Returns total active record count."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM episodic_memories WHERE is_active = 1")
            row = cursor.fetchone()
            return row[0] if row else 0

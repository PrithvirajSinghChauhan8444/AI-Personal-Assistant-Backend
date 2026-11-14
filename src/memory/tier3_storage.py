"""Tier 3 Episodic Memory Storage engine backed by SQLite and FAISS."""

import json
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

import faiss
import numpy as np

from src.memory.contracts import (
    EpisodicRecord,
    MemorySearchResponse,
    MemorySearchResult,
    RetrievalTelemetry,
)
from src.memory.embeddings import EmbeddingEngineProtocol, create_embedder

DEFAULT_SIMILARITY_THRESHOLD = 0.70


class EpisodicMemoryStore:
    """Manages long-term factual memories via SQLite metadata and FAISS vector indexing."""

    def __init__(
        self,
        db_path: str,
        index_path: str,
        embedder: Optional[EmbeddingEngineProtocol] = None,
        min_relevance_score: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        self.db_path = os.path.abspath(os.path.expanduser(db_path))
        self.index_path = os.path.abspath(os.path.expanduser(index_path))
        self.min_relevance_score = min_relevance_score
        self.embedder = embedder or create_embedder()

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        self._init_sqlite()
        self._index = self._load_or_create_index()

    def _init_sqlite(self) -> None:
        """Initializes the SQLite episodic_memories schema."""
        with sqlite3.connect(self.db_path) as conn:
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
                    updated_at INTEGER NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_cat ON episodic_memories(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_time ON episodic_memories(created_at DESC);")
            conn.commit()

    def _load_or_create_index(self) -> faiss.IndexIDMap2:
        """Loads FAISS index from disk or creates a fresh IndexFlatIP."""
        dim = self.embedder.dimension
        if os.path.isfile(self.index_path):
            try:
                loaded = faiss.read_index(self.index_path)
                # Verify loaded index matches dimension
                if loaded.d == dim:
                    if isinstance(loaded, faiss.IndexIDMap2):
                        return loaded
                    return faiss.IndexIDMap2(loaded)
            except Exception:
                pass

        sub_index = faiss.IndexFlatIP(dim)
        return faiss.IndexIDMap2(sub_index)

    def _save_index(self) -> None:
        """Persists FAISS index to disk."""
        faiss.write_index(self._index, self.index_path)

    def store_fact(
        self,
        content: str,
        category: str = "note",
        tags: Optional[List[str]] = None,
        source_session_id: Optional[str] = None,
        source_turn_id: Optional[str] = None,
        confidence: float = 1.0,
    ) -> EpisodicRecord:
        """Embeds and persists an atomic factual memory into SQLite and FAISS."""
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Memory content cannot be empty.")

        clean_category = category.strip().lower() or "note"
        clean_tags = [t.strip() for t in (tags or []) if t.strip()]
        tags_json = json.dumps(clean_tags)

        now_ms = int(time.time() * 1000)
        mem_id = f"mem_{uuid.uuid4().hex[:12]}"
        vector = self.embedder.embed_text(clean_content)
        dim = len(vector)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO episodic_memories (
                    id, content, category, tags, source_session_id, source_turn_id,
                    confidence, embedding_dim, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mem_id,
                    clean_content,
                    clean_category,
                    tags_json,
                    source_session_id,
                    source_turn_id,
                    confidence,
                    dim,
                    now_ms,
                    now_ms,
                ),
            )
            auto_id = cursor.lastrowid
            conn.commit()

        # Add to FAISS index with auto_id
        np_vector = np.array([vector], dtype=np.float32)
        id_array = np.array([auto_id], dtype=np.int64)
        self._index.add_with_ids(np_vector, id_array)
        self._save_index()

        return EpisodicRecord(
            id=mem_id,
            content=clean_content,
            category=clean_category,
            tags=clean_tags,
            source_session_id=source_session_id,
            source_turn_id=source_turn_id,
            confidence=confidence,
            embedding_dim=dim,
            created_at=now_ms,
            updated_at=now_ms,
        )

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3,
    ) -> MemorySearchResponse:
        """Retrieves memories using semantic vector similarity with >=0.70 cutoff."""
        clean_query = query.strip()
        if not clean_query or self._index.ntotal == 0:
            telemetry = RetrievalTelemetry(
                embed_latency_ms=0.0,
                index_latency_ms=0.0,
                top_score=0.0,
                chunks_returned=0,
            )
            return MemorySearchResponse(results=[], telemetry=telemetry)

        # 1. Embed query vector
        t0 = time.perf_counter()
        query_vector = self.embedder.embed_text(clean_query)
        embed_latency_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Vector search in FAISS
        t1 = time.perf_counter()
        np_query = np.array([query_vector], dtype=np.float32)
        probe_k = min(self._index.ntotal, max(top_k * 4, 10))
        distances, indices = self._index.search(np_query, probe_k)
        index_latency_ms = (time.perf_counter() - t1) * 1000.0

        raw_scores = distances[0]
        raw_ids = indices[0]

        # 3. Filter candidates by score cutoff >= 0.70 and valid auto_id
        candidates: List[tuple[int, float]] = []
        for auto_id, score in zip(raw_ids, raw_scores):
            if auto_id != -1 and score >= self.min_relevance_score:
                candidates.append((int(auto_id), float(score)))

        if not candidates:
            telemetry = RetrievalTelemetry(
                embed_latency_ms=embed_latency_ms,
                index_latency_ms=index_latency_ms,
                top_score=float(raw_scores[0]) if len(raw_scores) > 0 else 0.0,
                chunks_returned=0,
            )
            return MemorySearchResponse(results=[], telemetry=telemetry)

        # 4. Hydrate SQLite records
        target_ids = [c[0] for c in candidates]
        placeholders = ",".join("?" for _ in target_ids)
        records_by_auto_id: Dict[int, EpisodicRecord] = {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT auto_id, id, content, category, tags, source_session_id,
                       source_turn_id, confidence, embedding_dim, created_at, updated_at
                FROM episodic_memories
                WHERE auto_id IN ({placeholders})
                """,
                target_ids,
            )
            for row in cursor.fetchall():
                aid = row[0]
                records_by_auto_id[aid] = EpisodicRecord(
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
                )

        # 5. Filter by category if requested, and sort
        matched_results: List[MemorySearchResult] = []
        filter_cat = category.strip().lower() if category else None

        rank = 1
        for auto_id, score in candidates:
            record = records_by_auto_id.get(auto_id)
            if not record:
                continue
            if filter_cat and record.category.lower() != filter_cat:
                continue

            matched_results.append(MemorySearchResult(record=record, score=score, rank=rank))
            rank += 1
            if len(matched_results) >= top_k:
                break

        top_score = matched_results[0].score if matched_results else (candidates[0][1] if candidates else 0.0)
        telemetry = RetrievalTelemetry(
            embed_latency_ms=embed_latency_ms,
            index_latency_ms=index_latency_ms,
            top_score=top_score,
            chunks_returned=len(matched_results),
        )

        return MemorySearchResponse(results=matched_results, telemetry=telemetry)

    def delete(self, memory_id: str, reason: Optional[str] = None) -> bool:
        """Deletes a memory record by string ID from SQLite and FAISS."""
        clean_id = memory_id.strip()
        auto_id: Optional[int] = None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT auto_id FROM episodic_memories WHERE id = ?", (clean_id,))
            row = cursor.fetchone()
            if row:
                auto_id = row[0]
                cursor.execute("DELETE FROM episodic_memories WHERE id = ?", (clean_id,))
                conn.commit()

        if auto_id is not None:
            self._index.remove_ids(np.array([auto_id], dtype=np.int64))
            self._save_index()
            return True

        return False

    def get_by_id(self, memory_id: str) -> Optional[EpisodicRecord]:
        """Fetches a single memory record by its string ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, category, tags, source_session_id, source_turn_id,
                       confidence, embedding_dim, created_at, updated_at
                FROM episodic_memories
                WHERE id = ?
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
            )

    @property
    def total_records(self) -> int:
        """Returns the total number of episodic memory records in SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM episodic_memories")
            row = cursor.fetchone()
            return row[0] if row else 0

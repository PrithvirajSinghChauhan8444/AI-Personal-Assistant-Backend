"""Episodic Memory Storage engine backed by SQLite repository and FAISS vector index."""

import logging
import time
import uuid
from typing import List, Optional, Tuple

from src.memory.contracts import (
    EpisodicRecord,
    MemorySearchResponse,
    MemorySearchResult,
    RetrievalTelemetry,
)
from src.memory.embeddings import EmbeddingEngineProtocol, create_embedder
from src.memory.storage.faiss_index import FaissIndexManager
from src.memory.storage.process_lock import ProcessLock
from src.memory.storage.sqlite_repository import EpisodicSqliteRepository
from src.memory.storage.temporal_ranker import (
    RECENCY_HALF_LIFE_DAYS,
    rank_and_package_results,
)

logger = logging.getLogger(__name__)

DEFAULT_SIMILARITY_THRESHOLD = 0.60
SEMANTIC_SUPERSEDE_THRESHOLD = 0.96


class EpisodicMemoryStore:
    """Manages long-term factual memories via SQLite metadata and FAISS vector indexing."""

    def __init__(
        self,
        db_path: str,
        index_path: str,
        embedder: Optional[EmbeddingEngineProtocol] = None,
        min_relevance_score: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        self.db_path = db_path
        self.index_path = index_path
        self.min_relevance_score = min_relevance_score
        self.embedder = embedder or create_embedder()

        self._lock = ProcessLock(f"{self.index_path}.lock")
        self.repository = EpisodicSqliteRepository(self.db_path)
        self.index_manager = FaissIndexManager(
            index_path=self.index_path,
            dimension=self.embedder.dimension,
            lock=self._lock,
        )
        self._reconcile_index_if_needed()

    def _reconcile_index_if_needed(self) -> None:
        """Reconstructs FAISS vector index from SQLite if counts desynchronize."""
        active_count = self.repository.count_active()
        if active_count > 0 and self.index_manager.total_vectors != active_count:
            logger.info(
                "Reconciling FAISS index (index ntotal=%d, sqlite active=%d)...",
                self.index_manager.total_vectors,
                active_count,
            )
            self.rebuild_index_from_sqlite()

    def rebuild_index_from_sqlite(self) -> int:
        """Rebuilds the entire FAISS index directly from active records in SQLite."""
        active_rows = self.repository.get_all_active_for_rebuild()
        if not active_rows:
            return self.index_manager.rebuild([], [])

        auto_ids = [r[0] for r in active_rows]
        texts = [r[1] for r in active_rows]
        vectors = self.embedder.embed_batch(texts)
        return self.index_manager.rebuild(auto_ids, vectors)

    def store_fact(
        self,
        content: str,
        category: str = "note",
        tags: Optional[List[str]] = None,
        source_session_id: Optional[str] = None,
        source_turn_id: Optional[str] = None,
        confidence: float = 1.0,
    ) -> EpisodicRecord:
        """Embeds and persists an atomic factual memory with deduplication and versioning."""
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Memory content cannot be empty.")

        clean_category = category.strip().lower() or "note"
        clean_tags = [t.strip() for t in (tags or []) if t.strip()]
        now_ms = int(time.time() * 1000)

        # 1. Exact Duplicate Check
        existing = self.repository.find_exact_active_fact(clean_content, clean_category)
        if existing is not None:
            auto_id, rec = existing
            merged_tags = list(dict.fromkeys(rec.tags + clean_tags))
            self.repository.update_tags(auto_id, merged_tags, now_ms)
            rec.tags = merged_tags
            rec.updated_at = now_ms
            return rec

        # 2. Semantic Near-Duplicate Check
        vector = self.embedder.embed_text(clean_content)
        dim = len(vector)
        supersedes_id, new_version = self._check_semantic_supersession(vector, clean_category, now_ms)

        # 3. Insert fresh record into SQLite
        mem_id = f"mem_{uuid.uuid4().hex[:12]}"
        auto_id = self.repository.insert_record(
            mem_id=mem_id,
            content=clean_content,
            category=clean_category,
            tags=clean_tags,
            source_session_id=source_session_id,
            source_turn_id=source_turn_id,
            confidence=confidence,
            embedding_dim=dim,
            supersedes_id=supersedes_id,
            version=new_version,
            timestamp_ms=now_ms,
        )

        # 4. Add to FAISS index
        self.index_manager.add_vector(auto_id, vector)

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
            is_active=True,
            supersedes=supersedes_id,
            version=new_version,
        )

    def _check_semantic_supersession(
        self, vector: List[float], clean_category: str, now_ms: int
    ) -> Tuple[Optional[str], int]:
        """Detects near-duplicate in same category and marks superseded."""
        supersedes_id: Optional[str] = None
        new_version = 1

        if self.index_manager.total_vectors > 0:
            scores, ids = self.index_manager.search_nearest(vector, 1)
            if scores and scores[0] >= SEMANTIC_SUPERSEDE_THRESHOLD:
                near_auto_id = ids[0]
                if near_auto_id != -1:
                    info = self.repository.get_superseded_info(near_auto_id)
                    if info and info[1].lower() == clean_category:
                        supersedes_id = info[0]
                        new_version = info[2] + 1
                        self.repository.soft_delete(near_auto_id, "superseded", now_ms)
                        self.index_manager.remove_ids([near_auto_id])

        return (supersedes_id, new_version)

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3,
    ) -> MemorySearchResponse:
        """Retrieves memories using semantic vector similarity and temporal recency decay."""
        clean_query = query.strip()
        if not clean_query or self.index_manager.total_vectors == 0:
            telemetry = RetrievalTelemetry(
                embed_latency_ms=0.0,
                index_latency_ms=0.0,
                top_score=0.0,
                chunks_returned=0,
            )
            return MemorySearchResponse(results=[], telemetry=telemetry)

        # 1. Embed query
        t0 = time.perf_counter()
        if hasattr(self.embedder, "embed_query"):
            query_vector = self.embedder.embed_query(clean_query)
        else:
            query_vector = self.embedder.embed_text(clean_query)
        embed_latency_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Dynamic probe depth
        t1 = time.perf_counter()
        total_vectors = self.index_manager.total_vectors
        probe_k = min(total_vectors, max(top_k * 10, 50)) if category else min(total_vectors, max(top_k * 4, 10))
        raw_scores, raw_ids = self.index_manager.search_nearest(query_vector, probe_k)
        index_latency_ms = (time.perf_counter() - t1) * 1000.0

        # 3. Filter candidates by threshold
        candidates: List[Tuple[int, float]] = []
        for auto_id, score in zip(raw_ids, raw_scores):
            if auto_id != -1 and score >= self.min_relevance_score:
                candidates.append((auto_id, float(score)))

        if not candidates:
            telemetry = RetrievalTelemetry(
                embed_latency_ms=embed_latency_ms,
                index_latency_ms=index_latency_ms,
                top_score=float(raw_scores[0]) if raw_scores else 0.0,
                chunks_returned=0,
            )
            return MemorySearchResponse(results=[], telemetry=telemetry)

        # 4. Hydrate & Rank
        target_ids = [c[0] for c in candidates]
        records_by_auto_id = self.repository.hydrate_records(target_ids)
        now_ms = int(time.time() * 1000)

        matched_results = rank_and_package_results(
            records_by_auto_id=records_by_auto_id,
            candidates=candidates,
            category_filter=category,
            top_k=top_k,
            now_ms=now_ms,
        )

        top_score = matched_results[0].score if matched_results else (candidates[0][1] if candidates else 0.0)
        telemetry = RetrievalTelemetry(
            embed_latency_ms=embed_latency_ms,
            index_latency_ms=index_latency_ms,
            top_score=top_score,
            chunks_returned=len(matched_results),
        )

        return MemorySearchResponse(results=matched_results, telemetry=telemetry)

    def delete(self, memory_id: str, reason: Optional[str] = None) -> bool:
        """Deletes a memory record with audit trail, updating SQLite and FAISS."""
        auto_id = self.repository.find_auto_id_by_string_id(memory_id)
        if auto_id is None:
            return False

        now_ms = int(time.time() * 1000)
        self.repository.soft_delete(auto_id, reason or "user_deleted", now_ms)
        self.index_manager.remove_ids([auto_id])
        return True

    def get_by_id(self, memory_id: str) -> Optional[EpisodicRecord]:
        """Fetches a single active memory record by its string ID."""
        return self.repository.get_by_id(memory_id)

    @property
    def total_records(self) -> int:
        """Returns the total number of active episodic memory records in SQLite."""
        return self.repository.count_active()

"""Temporal recency decay and relevance ranking calculations for episodic search."""

from typing import Dict, List, Optional, Tuple

from src.memory.contracts import EpisodicRecord, MemorySearchResult

RECENCY_HALF_LIFE_DAYS = 30.0


def compute_temporal_decay(created_at_ms: int, now_ms: int, half_life_days: float = RECENCY_HALF_LIFE_DAYS) -> float:
    """Computes exponential decay factor based on record age."""
    age_days = (now_ms - created_at_ms) / (1000.0 * 86400.0)
    return float(0.5 ** (max(0.0, age_days) / half_life_days))


def compute_blended_score(raw_score: float, time_decay: float, vector_weight: float = 0.85) -> float:
    """Combines vector cosine similarity and temporal decay into a single relevance score."""
    decay_weight = 1.0 - vector_weight
    return (raw_score * vector_weight) + (time_decay * decay_weight)


def rank_and_package_results(
    records_by_auto_id: Dict[int, EpisodicRecord],
    candidates: List[Tuple[int, float]],
    category_filter: Optional[str],
    top_k: int,
    now_ms: int,
) -> List[MemorySearchResult]:
    """Applies category filtering, temporal decay blending, and ranking to hydrated candidate records."""
    matched_items: List[Tuple[EpisodicRecord, float]] = []
    clean_cat = category_filter.strip().lower() if category_filter else None

    for auto_id, raw_score in candidates:
        record = records_by_auto_id.get(auto_id)
        if not record:
            continue
        if clean_cat and record.category.lower() != clean_cat:
            continue

        time_decay = compute_temporal_decay(record.created_at, now_ms)
        blended_score = compute_blended_score(raw_score, time_decay)
        matched_items.append((record, blended_score))

    matched_items.sort(key=lambda x: x[1], reverse=True)

    results: List[MemorySearchResult] = []
    for rank, (record, score) in enumerate(matched_items[:top_k], 1):
        results.append(MemorySearchResult(record=record, score=score, rank=rank))

    return results

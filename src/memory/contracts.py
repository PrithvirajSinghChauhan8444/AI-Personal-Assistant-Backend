"""Contracts, models, and protocols for Layer 5 Memory Engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class MemoryCategory(str, Enum):
    """Supported categories for long-term episodic memory storage."""
    PROJECT = "project"
    SYSTEM = "system"
    CONVERSATION = "conversation"
    NOTE = "note"


@dataclass
class EpisodicRecord:
    """Archival fact or episodic snippet stored in SQLite and FAISS."""
    id: str
    content: str
    category: str
    source_session_id: Optional[str] = None
    source_turn_id: Optional[str] = None
    confidence: float = 1.0
    embedding_dim: int = 384
    tags: List[str] = field(default_factory=list)
    created_at: int = 0
    updated_at: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "source_session_id": self.source_session_id,
            "source_turn_id": self.source_turn_id,
            "confidence": self.confidence,
            "embedding_dim": self.embedding_dim,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class MemorySearchResult:
    """Individual retrieved memory entry with semantic score."""
    record: EpisodicRecord
    score: float
    rank: int


@dataclass
class RetrievalTelemetry:
    """Performance and relevance metrics for a semantic retrieval query."""
    embed_latency_ms: float
    index_latency_ms: float
    top_score: float
    chunks_returned: int


@dataclass
class MemorySearchResponse:
    """Composite response returned by memory search engine."""
    results: List[MemorySearchResult]
    telemetry: RetrievalTelemetry

    def format_text(self) -> str:
        """Formats the search results into a clean readable string for the model."""
        if not self.results:
            return "No matching memories found."

        lines = [f"Found {len(self.results)} relevant memories:"]
        for idx, item in enumerate(self.results, 1):
            tags_str = f" [tags: {', '.join(item.record.tags)}]" if item.record.tags else ""
            lines.append(
                f"{idx}. [{item.record.id}] ({item.record.category}, score: {item.score:.2f}){tags_str}: {item.record.content}"
            )
        return "\n".join(lines)


@dataclass
class ReflectionAction:
    """Individual memory mutation action derived from reflection analysis."""
    action_type: str  # 'update_profile', 'store_fact', or 'noop'
    section: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    reason: str = ""


@runtime_checkable
class EmbeddingEngineProtocol(Protocol):
    """Protocol for local vector embedding generation."""

    @property
    def dimension(self) -> int:
        """Returns the embedding vector dimensionality."""
        ...

    def embed_text(self, text: str) -> List[float]:
        """Generates a normalized dense embedding vector for a single text."""
        ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates normalized dense embedding vectors for a batch of texts."""
        ...

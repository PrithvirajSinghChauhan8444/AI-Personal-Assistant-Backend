"""Unified Layer 5 Memory Layer Package."""

from src.memory.contracts import (
    EpisodicRecord,
    MemoryContextSnapshot,
    MemoryMutationEvent,
    MemoryObserver,
    MemorySearchResponse,
    MemorySearchResult,
    ReflectionAction,
    RetrievedFactSnapshot,
)
from src.memory.embeddings import (
    DeterministicMockEmbedder,
    EmbeddingEngineProtocol,
    FastEmbedEmbedder,
    SentenceTransformerEmbedder,
    create_embedder,
)
from src.memory.engine import MemoryEngine, resolve_memory_base_dir
from src.memory.profiles import AccountsContextManager, UserProfileManager
from src.memory.reflection import MemoryReflectionAgent
from src.memory.storage import (
    DEFAULT_SIMILARITY_THRESHOLD,
    RECENCY_HALF_LIFE_DAYS,
    EpisodicMemoryStore,
)
from src.memory.tools import MEMORY_TOOLS, MemoryToolExecutor

__all__ = [
    "AccountsContextManager",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DeterministicMockEmbedder",
    "EmbeddingEngineProtocol",
    "EpisodicMemoryStore",
    "EpisodicRecord",
    "FastEmbedEmbedder",
    "MemoryContextSnapshot",
    "MemoryEngine",
    "MemoryMutationEvent",
    "MemoryObserver",
    "MemoryReflectionAgent",
    "MemorySearchResponse",
    "MemorySearchResult",
    "MemoryToolExecutor",
    "MEMORY_TOOLS",
    "RECENCY_HALF_LIFE_DAYS",
    "ReflectionAction",
    "RetrievedFactSnapshot",
    "SentenceTransformerEmbedder",
    "UserProfileManager",
    "create_embedder",
    "resolve_memory_base_dir",
]

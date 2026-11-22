"""Embedding generation abstractions for Layer 5 Memory Layer."""

import hashlib
import logging
import math
from typing import List, Optional

from src.memory.contracts import EmbeddingEngineProtocol

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_EMBEDDING_DIM = 384
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _apply_query_prefix(model_name: str, query: str) -> str:
    """Applies asymmetric search prefix for models that require it (e.g. BGE)."""
    clean_query = query.strip()
    if "bge" in model_name.lower():
        if not clean_query.startswith(BGE_QUERY_PREFIX):
            return f"{BGE_QUERY_PREFIX}{clean_query}"
    return clean_query


class DeterministicMockEmbedder:
    """Zero-dependency unit-norm mock embedder for deterministic, 0ms unit tests."""

    def __init__(self, dimension: int = DEFAULT_EMBEDDING_DIM) -> None:
        self._dimension = dimension
        self.is_fallback = False

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> List[float]:
        vector: List[float] = []
        for i in range(self._dimension):
            seed_string = f"{text}:{i}"
            digest = hashlib.sha256(seed_string.encode("utf-8")).hexdigest()
            val = (int(digest[:8], 16) / 0xFFFFFFFF) - 0.5
            vector.append(val)

        # L2 normalize so dot product equals cosine similarity
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            return [v / norm for v in vector]
        return [0.0] * self._dimension

    def embed_query(self, query: str) -> List[float]:
        return self.embed_text(query)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class SentenceTransformerEmbedder:
    """Generates normalized vector embeddings via local SentenceTransformers."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = None
        self._dim = DEFAULT_EMBEDDING_DIM
        self._fallback_mock: Optional[DeterministicMockEmbedder] = None

    @property
    def is_fallback(self) -> bool:
        return self._fallback_mock is not None

    def _ensure_loaded(self) -> None:
        if self._model is not None or self._fallback_mock is not None:
            return

        import os
        import warnings
        from contextlib import redirect_stderr

        # Silence noisy unauthenticated ping warnings and progress bars from HuggingFace
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
        logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
        logging.getLogger("transformers").setLevel(logging.ERROR)
        warnings.filterwarnings("ignore", category=FutureWarning)
        warnings.filterwarnings("ignore", module="huggingface_hub")
        warnings.filterwarnings("ignore", module="sentence_transformers")

        try:
            import transformers
            transformers.logging.set_verbosity_error()
        except Exception:
            pass

        try:
            from sentence_transformers import SentenceTransformer

            # Suppress C-level and python stderr noise during model loading
            with open(os.devnull, "w") as fnull, redirect_stderr(fnull):
                try:
                    self._model = SentenceTransformer(self.model_name, local_files_only=True)
                except Exception:
                    self._model = SentenceTransformer(self.model_name)

            get_dim = getattr(
                self._model,
                "get_embedding_dimension",
                getattr(self._model, "get_sentence_embedding_dimension", None),
            )
            if callable(get_dim):
                self._dim = get_dim()
        except Exception as exc:
            logger.warning(
                "Could not load SentenceTransformer '%s': %s. Degrading to DeterministicMockEmbedder.",
                self.model_name,
                exc,
            )
            self._fallback_mock = DeterministicMockEmbedder(self._dim)
            self._fallback_mock.is_fallback = True

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        self._ensure_loaded()
        if self._fallback_mock:
            return self._fallback_mock.embed_text(text)
        embedding = self._model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return embedding.tolist()

    def embed_query(self, query: str) -> List[float]:
        prefixed = _apply_query_prefix(self.model_name, query)
        return self.embed_text(prefixed)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        self._ensure_loaded()
        if self._fallback_mock:
            return self._fallback_mock.embed_batch(texts)
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [e.tolist() for e in embeddings]


class FastEmbedEmbedder:
    """Generates normalized vector embeddings via local ONNX fastembed runtime."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = None
        self._dim = DEFAULT_EMBEDDING_DIM
        self._fallback_mock: Optional[DeterministicMockEmbedder] = None

    @property
    def is_fallback(self) -> bool:
        return self._fallback_mock is not None

    def _ensure_loaded(self) -> None:
        if self._model is not None or self._fallback_mock is not None:
            return

        try:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self.model_name)
            probe = list(self._model.embed(["probe"]))[0]
            self._dim = len(probe)
        except Exception as exc:
            logger.warning(
                "Could not load FastEmbed model '%s': %s. Degrading to DeterministicMockEmbedder.",
                self.model_name,
                exc,
            )
            self._fallback_mock = DeterministicMockEmbedder(self._dim)
            self._fallback_mock.is_fallback = True

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        self._ensure_loaded()
        if self._fallback_mock:
            return self._fallback_mock.embed_text(text)
        vector = list(self._model.embed([text]))[0]
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            return [float(v / norm) for v in vector]
        return [float(v) for v in vector]

    def embed_query(self, query: str) -> List[float]:
        prefixed = _apply_query_prefix(self.model_name, query)
        return self.embed_text(prefixed)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        self._ensure_loaded()
        if self._fallback_mock:
            return self._fallback_mock.embed_batch(texts)
        vectors = list(self._model.embed(texts))
        results: List[List[float]] = []
        for vec in vectors:
            norm = math.sqrt(sum(v * v for v in vec))
            results.append([float(v / norm) for v in vec] if norm > 0 else [float(v) for v in vec])
        return results


def create_embedder(provider: Optional[str] = None, model_name: Optional[str] = None) -> EmbeddingEngineProtocol:
    """Factory creating the appropriate embedding engine based on user configuration."""
    import os

    env_provider = os.environ.get("AI_ASSISTANT_MEMORY_EMBEDDER")
    env_model = os.environ.get("AI_ASSISTANT_MEMORY_EMBEDDING_MODEL")

    if not provider or not model_name:
        try:
            from src.agents.factory import load_system_config
            cfg = load_system_config()
            provider = provider or cfg.get("memory_embedding_provider")
            model_name = model_name or cfg.get("memory_embedding_model")
        except Exception:
            pass

    provider_clean = (provider or env_provider or "onnx").lower()
    target_model = model_name or env_model or DEFAULT_MODEL_NAME

    if provider_clean in ("mock", "test"):
        return DeterministicMockEmbedder()

    if provider_clean in ("onnx", "fastembed"):
        try:
            return FastEmbedEmbedder(model_name=target_model)
        except Exception:
            return SentenceTransformerEmbedder(model_name=target_model)

    if provider_clean in ("huggingface", "sentence_transformers"):
        return SentenceTransformerEmbedder(model_name=target_model)

    # Default to ONNX
    return FastEmbedEmbedder(model_name=target_model)

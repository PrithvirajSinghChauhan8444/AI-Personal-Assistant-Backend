"""FAISS Vector Index manager for memory embedding searches."""

import logging
import os
import tempfile
from typing import List, Optional, Tuple

import faiss
import numpy as np

from src.memory.storage.process_lock import ProcessLock

logger = logging.getLogger(__name__)


class FaissIndexManager:
    """Encapsulates FAISS IndexIDMap2 lifecycle, serialization, and vector operations."""

    def __init__(self, index_path: str, dimension: int, lock: ProcessLock) -> None:
        self.index_path = os.path.abspath(os.path.expanduser(index_path))
        self.dimension = dimension
        self.lock = lock
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        self._index: faiss.IndexIDMap2 = self._load_or_create()

    def _load_or_create(self) -> faiss.IndexIDMap2:
        """Loads FAISS index from disk under lock or creates a fresh IndexFlatIP."""
        with self.lock.acquire():
            if os.path.isfile(self.index_path):
                try:
                    loaded = faiss.read_index(self.index_path)
                    if loaded.d == self.dimension:
                        if isinstance(loaded, faiss.IndexIDMap2):
                            return loaded
                        return faiss.IndexIDMap2(loaded)
                except Exception as exc:
                    logger.warning(
                        "Could not load FAISS index from %s (%s); creating fresh index.",
                        self.index_path,
                        exc,
                    )

            sub_index = faiss.IndexFlatIP(self.dimension)
            return faiss.IndexIDMap2(sub_index)

    def save(self) -> None:
        """Atomically saves FAISS index to disk under file lock."""
        with self.lock.acquire():
            dir_name = os.path.dirname(self.index_path)
            temp_file = tempfile.NamedTemporaryFile(dir=dir_name, delete=False, suffix=".tmp")
            temp_path = temp_file.name
            temp_file.close()
            try:
                faiss.write_index(self._index, temp_path)
                os.replace(temp_path, self.index_path)
            except Exception:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                raise

    @property
    def total_vectors(self) -> int:
        """Returns number of indexed vectors."""
        return self._index.ntotal

    def search_nearest(self, vector: List[float], k: int) -> Tuple[List[float], List[int]]:
        """Searches index for nearest k vectors. Returns (scores, ids)."""
        if self._index.ntotal == 0 or k <= 0:
            return ([], [])

        np_vec = np.array([vector], dtype=np.float32)
        distances, indices = self._index.search(np_vec, k)
        return (list(distances[0]), [int(i) for i in indices[0]])

    def add_vector(self, auto_id: int, vector: List[float]) -> None:
        """Adds a single vector with associated auto_id under lock and persists."""
        with self.lock.acquire():
            np_vector = np.array([vector], dtype=np.float32)
            id_array = np.array([auto_id], dtype=np.int64)
            self._index.add_with_ids(np_vector, id_array)
        self.save()

    def remove_ids(self, auto_ids: List[int]) -> None:
        """Removes a list of IDs from index under lock and persists."""
        if not auto_ids or self._index.ntotal == 0:
            return
        with self.lock.acquire():
            self._index.remove_ids(np.array(auto_ids, dtype=np.int64))
        self.save()

    def rebuild(self, auto_ids: List[int], vectors: List[List[float]]) -> int:
        """Rebuilds the entire index from scratch under lock."""
        with self.lock.acquire():
            sub_index = faiss.IndexFlatIP(self.dimension)
            fresh_index = faiss.IndexIDMap2(sub_index)

            if auto_ids and vectors:
                np_vectors = np.array(vectors, dtype=np.float32)
                id_array = np.array(auto_ids, dtype=np.int64)
                fresh_index.add_with_ids(np_vectors, id_array)

            self._index = fresh_index
        self.save()
        return self._index.ntotal

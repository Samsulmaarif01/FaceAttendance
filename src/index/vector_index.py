"""
Nearest-neighbour vector index for face embeddings.

``BruteForceIndex`` is an exact cosine index implemented with numpy only, so the
system works on any CPU-only edge device with no extra dependencies.
``FAISSIndex`` is an optional backend (FAISS flat / HNSW, inner-product) that is
imported lazily; callers should check :func:`available_backends` or
``FAISSIndex.is_available`` and fall back to brute force when it is missing.

All vectors are L2-normalised on insert, so inner product equals cosine
similarity and scores are directly comparable to the recognition threshold.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

try:  # optional dependency
    import faiss  # type: ignore
except Exception:  # pragma: no cover - exercised only when faiss is present
    faiss = None


@dataclass(frozen=True)
class SearchHit:
    id: str
    score: float


def _normalize(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


class VectorIndex(ABC):
    @abstractmethod
    def add(self, vector_id: str, vector: np.ndarray) -> None:
        ...

    @abstractmethod
    def add_batch(self, ids: Sequence[str], vectors: np.ndarray) -> None:
        ...

    @abstractmethod
    def search(self, vector: np.ndarray, k: int = 1) -> List[SearchHit]:
        ...

    @abstractmethod
    def remove(self, vector_id: str) -> bool:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...

    @abstractmethod
    def __len__(self) -> int:
        ...


class BruteForceIndex(VectorIndex):
    """Exact cosine index backed by a numpy matrix. No external dependencies."""

    def __init__(self) -> None:
        self._ids: List[str] = []
        self._matrix: np.ndarray = np.empty((0, 0), dtype=np.float32)

    def add(self, vector_id: str, vector: np.ndarray) -> None:
        self.add_batch([vector_id], np.asarray(vector, dtype=np.float32)[None, :])

    def add_batch(self, ids: Sequence[str], vectors: np.ndarray) -> None:
        vectors = np.atleast_2d(np.asarray(vectors, dtype=np.float32))
        if vectors.shape[0] == 0:
            return
        normalized = np.vstack([_normalize(row) for row in vectors])
        for vector_id, row in zip(ids, normalized):
            if vector_id in self._ids:
                self._matrix[self._ids.index(vector_id)] = row
            else:
                self._ids.append(vector_id)
                if self._matrix.size == 0:
                    self._matrix = row[None, :].astype(np.float32)
                else:
                    self._matrix = np.vstack([self._matrix, row[None, :]])

    def search(self, vector: np.ndarray, k: int = 1) -> List[SearchHit]:
        if not self._ids or k <= 0:
            return []
        query = _normalize(vector)
        scores = self._matrix @ query
        k = min(k, len(self._ids))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [SearchHit(self._ids[i], float(scores[i])) for i in top]

    def remove(self, vector_id: str) -> bool:
        if vector_id not in self._ids:
            return False
        index = self._ids.index(vector_id)
        self._ids.pop(index)
        self._matrix = np.delete(self._matrix, index, axis=0)
        return True

    def clear(self) -> None:
        self._ids = []
        self._matrix = np.empty((0, 0), dtype=np.float32)

    def __len__(self) -> int:
        return len(self._ids)


class FAISSIndex(VectorIndex):
    """Optional FAISS-backed index (flat inner-product or HNSW)."""

    def __init__(self, dim: int, use_hnsw: bool = False, hnsw_m: int = 32, ef_search: int = 64):
        if faiss is None:
            raise RuntimeError("faiss is not installed")
        self.dim = dim
        base = (
            faiss.IndexHNSWFlat(dim, hnsw_m, faiss.METRIC_INNER_PRODUCT)
            if use_hnsw
            else faiss.IndexFlatIP(dim)
        )
        if use_hnsw and hasattr(base, "hnsw"):
            base.hnsw.efSearch = ef_search
        self._index = faiss.IndexIDMap2(base)
        self._ids: Dict[int, str] = {}
        self._next_key = 0

    @staticmethod
    def is_available() -> bool:
        return faiss is not None

    def add(self, vector_id: str, vector: np.ndarray) -> None:
        self.add_batch([vector_id], np.asarray(vector, dtype=np.float32)[None, :])

    def add_batch(self, ids: Sequence[str], vectors: np.ndarray) -> None:
        vectors = np.atleast_2d(np.asarray(vectors, dtype=np.float32))
        if vectors.shape[0] == 0:
            return
        normalized = np.vstack([_normalize(row) for row in vectors])
        keys = np.arange(self._next_key, self._next_key + len(ids), dtype=np.int64)
        self._index.add_with_ids(normalized, keys)
        for key, vector_id in zip(keys.tolist(), ids):
            self._ids[key] = vector_id
        self._next_key += len(ids)

    def search(self, vector: np.ndarray, k: int = 1) -> List[SearchHit]:
        if not self._ids or k <= 0:
            return []
        query = _normalize(vector)[None, :]
        distances, keys = self._index.search(query, min(k, len(self._ids)))
        hits: List[SearchHit] = []
        for score, key in zip(distances[0].tolist(), keys[0].tolist()):
            if key < 0:
                continue
            hits.append(SearchHit(self._ids[int(key)], float(score)))
        return hits

    def remove(self, vector_id: str) -> bool:
        for key, mapped in list(self._ids.items()):
            if mapped == vector_id:
                self._index.remove_ids(np.array([key], dtype=np.int64))
                del self._ids[key]
                return True
        return False

    def clear(self) -> None:
        self._index.reset()
        self._ids = {}
        self._next_key = 0

    def __len__(self) -> int:
        return len(self._ids)


def available_backends() -> List[str]:
    backends = ["brute_force"]
    if faiss is not None:
        backends.append("faiss")
    return backends


def create_index(
    backend: str = "auto",
    dim: Optional[int] = None,
    **kwargs,
) -> VectorIndex:
    """Factory: ``auto`` prefers FAISS when installed, else brute force."""
    if backend in ("auto", "faiss") and faiss is not None:
        if dim is None:
            raise ValueError("dim is required for the FAISS backend")
        return FAISSIndex(dim=dim, **kwargs)
    if backend == "faiss":
        raise RuntimeError("faiss is not installed")
    return BruteForceIndex()

"""
Hierarchical coarse-to-fine matching.

A light PCA projection (fit with numpy SVD, no scikit-learn) is used as a cheap
coarse filter: the query is compared against low-dimensional projections to
select a small candidate set, which is then re-scored with the full embeddings.
This keeps exact full-vector comparisons to a fraction of the gallery, which is
what makes search scale past a few thousand users.
"""

from typing import List, Optional, Sequence

import numpy as np

from src.index.vector_index import SearchHit, _normalize


class PCAReducer:
    """Principal component projection fitted with numpy's SVD."""

    def __init__(self, n_components: int = 128):
        if n_components <= 0:
            raise ValueError("n_components must be positive")
        self.n_components = n_components
        self.mean_: Optional[np.ndarray] = None
        self.components_: Optional[np.ndarray] = None
        self.singular_values_: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray) -> "PCAReducer":
        X = np.asarray(X, dtype=np.float32)
        if X.ndim != 2 or X.shape[0] == 0:
            raise ValueError("X must be a non-empty 2D array")
        self.mean_ = X.mean(axis=0)
        centered = X - self.mean_
        _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
        k = min(self.n_components, vt.shape[0])
        self.components_ = vt[:k]
        self.singular_values_ = singular_values[:k]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.components_ is None or self.mean_ is None:
            raise RuntimeError("PCAReducer must be fitted before transform")
        X = np.atleast_2d(np.asarray(X, dtype=np.float32))
        return (X - self.mean_) @ self.components_.T

    def explained_variance_ratio(self) -> np.ndarray:
        if self.singular_values_ is None:
            raise RuntimeError("PCAReducer must be fitted first")
        total = float(np.sum(self.singular_values_ ** 2))
        if total == 0.0:
            return np.zeros_like(self.singular_values_)
        return (self.singular_values_ ** 2) / total


class HierarchicalMatcher:
    """Coarse PCA preselection followed by exact full-vector refinement."""

    def __init__(self, coarse_dim: int = 128, coarse_candidates: int = 50):
        if coarse_candidates <= 0:
            raise ValueError("coarse_candidates must be positive")
        self.coarse_dim = coarse_dim
        self.coarse_candidates = coarse_candidates
        self._ids: List[str] = []
        self._full: Optional[np.ndarray] = None
        self._coarse: Optional[np.ndarray] = None
        self._pca: Optional[PCAReducer] = None
        self._dirty = True

    def add(self, vector_id: str, vector: np.ndarray) -> None:
        self.add_batch([vector_id], np.asarray(vector, dtype=np.float32)[None, :])

    def add_batch(self, ids: Sequence[str], vectors: np.ndarray) -> None:
        vectors = np.atleast_2d(np.asarray(vectors, dtype=np.float32))
        if vectors.shape[0] == 0:
            return
        for vector_id, row in zip(ids, vectors):
            normalized = _normalize(row)
            if vector_id in self._ids:
                self._full[self._ids.index(vector_id)] = normalized
            else:
                self._ids.append(vector_id)
                self._full = (
                    normalized[None, :]
                    if self._full is None
                    else np.vstack([self._full, normalized[None, :]])
                )
        self._dirty = True

    def remove(self, vector_id: str) -> bool:
        if vector_id not in self._ids:
            return False
        index = self._ids.index(vector_id)
        self._ids.pop(index)
        self._full = np.delete(self._full, index, axis=0)
        if len(self._ids) == 0:
            self._full = None
        self._dirty = True
        return True

    def search(self, vector: np.ndarray, k: int = 1) -> List[SearchHit]:
        if not self._ids or k <= 0:
            return []
        self._ensure_built()
        assert self._full is not None
        query = _normalize(vector)
        full_scores = self._full @ query

        if self._coarse is not None and len(self._ids) > self.coarse_candidates:
            coarse_query = self._pca.transform(query[None, :])[0]
            coarse_scores = self._coarse @ coarse_query
            candidate_count = min(self.coarse_candidates, len(self._ids))
            candidates = np.argpartition(-coarse_scores, candidate_count - 1)[:candidate_count]
            order = candidates[np.argsort(-full_scores[candidates])]
        else:
            order = np.argsort(-full_scores)

        top = order[: min(k, len(self._ids))]
        return [SearchHit(self._ids[i], float(full_scores[i])) for i in top]

    def __len__(self) -> int:
        return len(self._ids)

    def _ensure_built(self) -> None:
        if not self._dirty:
            return
        assert self._full is not None
        if len(self._ids) >= 2:
            self._pca = PCAReducer(n_components=min(self.coarse_dim, len(self._ids))).fit(self._full)
            self._coarse = self._pca.transform(self._full)
        else:
            self._pca = None
            self._coarse = None
        self._dirty = False

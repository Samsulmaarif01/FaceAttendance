"""
ANN-backed drop-in replacement for ``FaceMatcher``.

Keeps the same ``match(embedding, database)`` contract used by the pipeline, but
resolves the best candidate with a :class:`~src.index.vector_index.VectorIndex`
instead of a linear scan, and delegates thresholding/adaptive logic to a
composed :class:`~src.recognition.extractor.FaceMatcher`. The index is rebuilt
lazily whenever the gallery contents change (keyed by size and ids).
"""

from typing import Dict, Optional

import numpy as np

from src.index.vector_index import BruteForceIndex, VectorIndex
from src.recognition.extractor import FaceMatcher, MatchResult


class IndexedMatcher:
    def __init__(
        self,
        threshold: float = 0.45,
        index: Optional[VectorIndex] = None,
        adaptive_enabled: bool = True,
        min_threshold: float = 0.35,
        max_threshold: float = 0.55,
        update_rate: float = 0.05,
        history_size: int = 100,
    ):
        self.index: VectorIndex = index if index is not None else BruteForceIndex()
        self._thresholder = FaceMatcher(
            threshold=threshold,
            adaptive_enabled=adaptive_enabled,
            min_threshold=min_threshold,
            max_threshold=max_threshold,
            update_rate=update_rate,
            history_size=history_size,
        )
        self._signature = None

    def match(
        self,
        embedding: np.ndarray,
        database: Dict[str, np.ndarray],
    ) -> Optional[MatchResult]:
        if not database:
            return None
        self._ensure_index(database)
        hits = self.index.search(embedding, k=1)
        if not hits:
            return None
        best = hits[0]
        return self._thresholder.decide(best.id, best.score)

    def update_threshold(self, user_id: str, similarity: float) -> None:
        self._thresholder.update_threshold(user_id, similarity)

    def set_user_threshold(self, user_id: str, threshold: float) -> None:
        self._thresholder.set_user_threshold(user_id, threshold)

    def _ensure_index(self, database: Dict[str, np.ndarray]) -> None:
        signature = (len(database), tuple(sorted(database.keys())))
        if signature == self._signature:
            return
        self.index.clear()
        ids = list(database.keys())
        vectors = np.stack([np.asarray(database[user_id], dtype=np.float32) for user_id in ids])
        self.index.add_batch(ids, vectors)
        self._signature = signature

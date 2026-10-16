"""
Per-site sharding for the vector index.

Each site/location keeps only the embeddings it needs (its own users), which
shrinks the search space and lets sites be provisioned or dropped independently.
Queries can target a subset of sites, so a facility only searches its relevant
branches. The index type per shard is injectable (brute force today, FAISS
later) so the storage engine can be swapped without touching callers.
"""

from typing import Callable, Dict, List, Optional, Sequence, Set

import numpy as np

from src.index.vector_index import BruteForceIndex, SearchHit, VectorIndex

IndexFactory = Callable[[], VectorIndex]


class ShardedVectorIndex:
    def __init__(self, index_factory: Optional[IndexFactory] = None):
        self._factory: IndexFactory = index_factory or BruteForceIndex
        self._shards: Dict[str, VectorIndex] = {}

    def add(self, site_id: str, vector_id: str, vector: np.ndarray) -> None:
        self._shard(site_id).add(vector_id, vector)

    def add_batch(self, site_id: str, ids: Sequence[str], vectors: np.ndarray) -> None:
        self._shard(site_id).add_batch(ids, vectors)

    def search(
        self,
        vector: np.ndarray,
        k: int = 1,
        sites: Optional[Sequence[str]] = None,
    ) -> List[SearchHit]:
        if k <= 0:
            return []
        target = self._resolve_sites(sites)
        hits: List[SearchHit] = []
        for site_id in target:
            hits.extend(self._shards[site_id].search(vector, k))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:k]

    def remove(self, site_id: str, vector_id: str) -> bool:
        shard = self._shards.get(site_id)
        if shard is None:
            return False
        return shard.remove(vector_id)

    def shard(self, site_id: str) -> VectorIndex:
        """Return (creating if needed) the index backing ``site_id``."""
        return self._shard(site_id)

    def sites(self) -> List[str]:
        return sorted(self._shards)

    def clear(self, site_id: Optional[str] = None) -> None:
        if site_id is None:
            for shard in self._shards.values():
                shard.clear()
            self._shards.clear()
        elif site_id in self._shards:
            self._shards[site_id].clear()

    def __len__(self) -> int:
        return sum(len(shard) for shard in self._shards.values())

    def stats(self) -> Dict[str, int]:
        return {site_id: len(shard) for site_id, shard in sorted(self._shards.items())}

    def _resolve_sites(self, sites: Optional[Sequence[str]]) -> List[str]:
        if sites is None:
            return [site_id for site_id in self._shards if len(self._shards[site_id]) > 0]
        wanted: Set[str] = set(sites)
        return [
            site_id
            for site_id in self._shards
            if site_id in wanted and len(self._shards[site_id]) > 0
        ]

    def _shard(self, site_id: str) -> VectorIndex:
        if site_id not in self._shards:
            self._shards[site_id] = self._factory()
        return self._shards[site_id]

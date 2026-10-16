"""Scalability layer: vector index, hierarchical matching, sharding, management."""

from .hierarchical import HierarchicalMatcher, PCAReducer
from .management import SiteRecord, SiteRegistry
from .matcher import IndexedMatcher
from .sharding import ShardedVectorIndex
from .vector_index import (
    BruteForceIndex,
    FAISSIndex,
    SearchHit,
    VectorIndex,
    available_backends,
    create_index,
)

__all__ = [
    "SearchHit",
    "VectorIndex",
    "BruteForceIndex",
    "FAISSIndex",
    "available_backends",
    "create_index",
    "PCAReducer",
    "HierarchicalMatcher",
    "ShardedVectorIndex",
    "SiteRecord",
    "SiteRegistry",
    "IndexedMatcher",
]

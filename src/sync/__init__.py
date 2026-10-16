"""Offline-first sync: CRDT queue, backoff, zstd delta compression, and manager."""

from .backoff import ExponentialBackoff
from .compression import (
    apply_delta,
    compute_delta,
    compress,
    decompress,
    delta_from_bytes,
    delta_to_bytes,
    records_by_id,
    records_from_bytes,
    records_to_bytes,
)
from .crdt import LWWElementSet
from .queue import SyncQueue
from .signing import (
    generate_keypair,
    open_envelope,
    sign_envelope,
    sign_payload,
    verify_payload,
)
from .sync_manager import (
    NullTransport,
    OfflineError,
    SyncManager,
    SyncResult,
    SyncTransport,
)

__all__ = [
    "LWWElementSet",
    "ExponentialBackoff",
    "SyncQueue",
    "SyncManager",
    "SyncResult",
    "SyncTransport",
    "NullTransport",
    "OfflineError",
    "compress",
    "decompress",
    "records_to_bytes",
    "records_from_bytes",
    "records_by_id",
    "compute_delta",
    "apply_delta",
    "delta_to_bytes",
    "delta_from_bytes",
    "generate_keypair",
    "sign_payload",
    "verify_payload",
    "sign_envelope",
    "open_envelope",
]

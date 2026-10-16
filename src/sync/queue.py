"""
Store-and-forward sync queue backed by an LWW-Element-Set CRDT.

Records are appended locally while the device is offline. Each enqueue is a CRDT
``add`` and each acknowledgement is a CRDT ``remove`` (tombstone), so two queues
can be merged without conflicts regardless of the order updates arrived. The
queue applies backpressure so a long outage cannot exhaust storage: once
``max_size`` is reached it either rejects new records or rotates out the oldest
ones (``overflow_policy``).

Ordering (oldest first) is derived from a per-record logical timestamp rather
than dict insertion order, which keeps ``peek`` deterministic even after merges.
State is persisted as a zstd-compressed JSON blob.
"""

import os
from typing import Any, Dict, List, Mapping, Optional

from src.sync.compression import compress, decompress, from_json_bytes, to_json_bytes
from src.sync.crdt import LWWElementSet

_VALID_POLICIES = ("evict_oldest", "reject")
_ORDER_KEY = "_queued_at"


class SyncQueue:
    def __init__(
        self,
        max_size: int = 10000,
        persist_path: Optional[str] = None,
        overflow_policy: str = "evict_oldest",
        autosave: bool = True,
    ):
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        if overflow_policy not in _VALID_POLICIES:
            raise ValueError(
                f"overflow_policy must be one of {_VALID_POLICIES}, got {overflow_policy!r}"
            )

        self.max_size = max_size
        self.persist_path = persist_path
        self.overflow_policy = overflow_policy
        self.autosave = autosave
        self._crdt = LWWElementSet()
        self._clock = 0.0

        if persist_path and os.path.exists(persist_path):
            self.load()

    # -- public API -----------------------------------------------------
    def enqueue(self, record: Mapping[str, Any], timestamp: Optional[float] = None) -> bool:
        """Add or update a record. Returns False when rejected by backpressure."""
        key = record["id"]

        if not self._crdt.contains(key) and len(self._crdt) >= self.max_size:
            if self.overflow_policy == "reject":
                return False
            self._evict_oldest()

        ts = self._next_timestamp() if timestamp is None else timestamp
        self._observe(ts)
        value = dict(record)
        value[_ORDER_KEY] = ts
        self._crdt = self._crdt.add(key, value, ts)
        self._maybe_save()
        return True

    def peek(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return the oldest records (without internal fields) without removing."""
        records = [self._crdt.get(key) for key in self._ordered_keys()]
        public = [self._public(record) for record in records if record is not None]
        return public if limit is None else public[:limit]

    def ack(self, record_ids: List[str]) -> int:
        """Tombstone records confirmed as synced. Returns the number removed."""
        removed = 0
        for key in record_ids:
            if self._crdt.contains(key):
                self._crdt = self._crdt.remove(key, self._next_timestamp())
                removed += 1
        if removed:
            self._maybe_save()
        return removed

    def merge(self, other: "SyncQueue") -> "SyncQueue":
        """Merge another queue's CRDT state into this one (commutative)."""
        self._crdt = self._crdt.merge(other._crdt)
        self._clock = max(self._clock, other._clock)
        self._maybe_save()
        return self

    def compact(self) -> None:
        """Drop tombstoned keys, keeping only present records (bounds storage)."""
        fresh = LWWElementSet()
        for key in self._ordered_keys():
            value = self._crdt.get(key)
            if value is None:
                continue
            fresh = fresh.add(key, value, value.get(_ORDER_KEY, self._next_timestamp()))
        self._crdt = fresh
        self._maybe_save()

    def clear(self) -> None:
        self._crdt = LWWElementSet()
        self._maybe_save()

    def is_full(self) -> bool:
        return len(self._crdt) >= self.max_size

    def tombstones(self) -> int:
        return len(self._crdt.remove_set)

    def __len__(self) -> int:
        return len(self._crdt)

    def __contains__(self, record_id: str) -> bool:
        return self._crdt.contains(record_id)

    # -- persistence ----------------------------------------------------
    def save(self) -> None:
        if not self.persist_path:
            return
        if self.tombstones() > self.max_size:
            self.compact()
        directory = os.path.dirname(self.persist_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = {"clock": self._clock, "crdt": self._crdt.to_dict()}
        with open(self.persist_path, "wb") as f:
            f.write(compress(to_json_bytes(payload)))

    def load(self) -> None:
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        with open(self.persist_path, "rb") as f:
            payload = from_json_bytes(decompress(f.read()))
        self._crdt = LWWElementSet.from_dict(payload.get("crdt", {}))
        self._clock = float(payload.get("clock", 0.0))

    # -- internals ------------------------------------------------------
    def _next_timestamp(self) -> float:
        self._clock += 1.0
        return self._clock

    def _observe(self, timestamp: float) -> None:
        if timestamp > self._clock:
            self._clock = timestamp

    def _ordered_keys(self) -> List[str]:
        def sort_key(key: str) -> float:
            value = self._crdt.get(key)
            if isinstance(value, dict):
                return float(value.get(_ORDER_KEY, 0.0))
            return 0.0

        return sorted(self._crdt.keys(), key=sort_key)

    def _evict_oldest(self) -> None:
        keys = self._ordered_keys()
        if keys:
            self._crdt = self._crdt.remove(keys[0], self._next_timestamp())

    @staticmethod
    def _public(record: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in record.items() if key != _ORDER_KEY}

    def _maybe_save(self) -> None:
        if self.autosave and self.persist_path:
            self.save()

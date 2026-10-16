"""
LWW-Element-Set CRDT for conflict-free attendance synchronisation.

An element is considered present when its latest *add* timestamp is strictly
greater than its latest *remove* (tombstone) timestamp. Timestamps are provided
by the caller (logical clocks), so the type stays pure and testable.

``merge`` takes the per-key maximum add/remove timestamps, which makes it
commutative, associative and idempotent: replicas that have observed the same
updates converge to the same set regardless of the order the updates arrived.
Value conflicts at an identical add timestamp are broken deterministically by
the canonical JSON representation, so the result never depends on which replica
merges first.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_NEG_INF = float("-inf")


def _canonical(value: Any) -> str:
    """Stable string form used to break timestamp ties deterministically."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class LWWElementSet:
    """Immutable last-write-wins element set keyed by string identifiers."""

    add_set: Dict[str, float] = field(default_factory=dict)
    remove_set: Dict[str, float] = field(default_factory=dict)
    values: Dict[str, Any] = field(default_factory=dict)

    def add(self, key: str, value: Any, timestamp: float) -> "LWWElementSet":
        """Return a new set with ``key`` added/updated at ``timestamp``."""
        if timestamp < self.add_set.get(key, _NEG_INF):
            return self
        add_set = dict(self.add_set)
        values = dict(self.values)
        add_set[key] = timestamp
        values[key] = value
        return LWWElementSet(add_set, dict(self.remove_set), values)

    def remove(self, key: str, timestamp: float) -> "LWWElementSet":
        """Return a new set with ``key`` tombstoned at ``timestamp``."""
        if timestamp <= self.remove_set.get(key, _NEG_INF):
            return self
        remove_set = dict(self.remove_set)
        remove_set[key] = timestamp
        return LWWElementSet(dict(self.add_set), remove_set, dict(self.values))

    def contains(self, key: str) -> bool:
        return self.add_set.get(key, _NEG_INF) > self.remove_set.get(key, _NEG_INF)

    def get(self, key: str) -> Optional[Any]:
        if not self.contains(key):
            return None
        return self.values.get(key)

    def keys(self) -> List[str]:
        return sorted(key for key in self.add_set if self.contains(key))

    def elements(self) -> Dict[str, Any]:
        return {key: self.values.get(key) for key in self.keys()}

    def __len__(self) -> int:
        return sum(1 for key in self.add_set if self.contains(key))

    def merge(self, other: "LWWElementSet") -> "LWWElementSet":
        """Merge two replicas; order-independent and idempotent."""
        add_set = dict(self.add_set)
        values = dict(self.values)

        for key, timestamp in other.add_set.items():
            current = add_set.get(key, _NEG_INF)
            if timestamp > current:
                add_set[key] = timestamp
                values[key] = other.values.get(key)
            elif timestamp == current and key in other.values:
                mine = values.get(key)
                if mine is None or _canonical(other.values[key]) > _canonical(mine):
                    values[key] = other.values[key]

        remove_set = dict(self.remove_set)
        for key, timestamp in other.remove_set.items():
            if timestamp > remove_set.get(key, _NEG_INF):
                remove_set[key] = timestamp

        return LWWElementSet(add_set, remove_set, values)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "add_set": self.add_set,
            "remove_set": self.remove_set,
            "values": self.values,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LWWElementSet":
        return cls(
            dict(data.get("add_set", {})),
            dict(data.get("remove_set", {})),
            dict(data.get("values", {})),
        )

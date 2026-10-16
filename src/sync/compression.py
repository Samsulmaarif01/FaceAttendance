"""
Payload compression and delta encoding for sync uploads.

Serialises records to canonical JSON and compresses with zstd. Delta encoding
sends only what changed relative to a previously known snapshot (added, updated
and deleted records), which keeps bandwidth small for the common case where an
offline node accumulated a handful of attendance rows.
"""

import json
from typing import Any, Dict, List, Mapping, Sequence

import zstandard as zstd

_DEFAULT_LEVEL = 3


def _dumps(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _loads(blob: bytes) -> Any:
    return json.loads(blob.decode("utf-8"))


def to_json_bytes(obj: Any) -> bytes:
    """Canonical JSON encoding (public helper for queue persistence)."""
    return _dumps(obj)


def from_json_bytes(blob: bytes) -> Any:
    """Inverse of :func:`to_json_bytes`."""
    return _loads(blob)


def compress(data: bytes, level: int = _DEFAULT_LEVEL) -> bytes:
    return zstd.ZstdCompressor(level=level).compress(data)


def decompress(data: bytes) -> bytes:
    return zstd.ZstdDecompressor().decompress(data)


def records_to_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return compress(_dumps(list(records)))


def records_from_bytes(blob: bytes) -> List[Dict[str, Any]]:
    return _loads(decompress(blob))


def records_by_id(records: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {record["id"]: dict(record) for record in records}


def compute_delta(
    previous: Mapping[str, Mapping[str, Any]],
    current: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Return the changes needed to turn ``previous`` into ``current``."""
    added = [current[key] for key in current if key not in previous]
    updated = [
        current[key]
        for key in current
        if key in previous and current[key] != previous[key]
    ]
    deleted = [key for key in previous if key not in current]
    return {"added": added, "updated": updated, "deleted": deleted}


def apply_delta(
    base: Mapping[str, Mapping[str, Any]], delta: Mapping[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Apply a delta produced by :func:`compute_delta`; idempotent."""
    result: Dict[str, Dict[str, Any]] = {key: dict(value) for key, value in base.items()}
    for record in list(delta.get("added", [])) + list(delta.get("updated", [])):
        result[record["id"]] = dict(record)
    for key in delta.get("deleted", []):
        result.pop(key, None)
    return result


def delta_to_bytes(delta: Mapping[str, Any]) -> bytes:
    return compress(_dumps(delta))


def delta_from_bytes(blob: bytes) -> Dict[str, Any]:
    return _loads(decompress(blob))

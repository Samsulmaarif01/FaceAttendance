"""
Append-only, tamper-evident audit log.

Each event is linked to the previous one through a SHA-256 hash chain, so
removing or editing any line invalidates the chain (detected by verify_chain).
"""

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

GENESIS_HASH = "0" * 64


@dataclass
class AuditEvent:
    index: int
    timestamp: str
    event_type: str
    user_id: str
    details: Dict[str, Any]
    prev_hash: str
    hash: str


class AuditLog:
    def __init__(self, path: str = "logs/audit.log"):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    @staticmethod
    def _compute_hash(
        index: int,
        timestamp: str,
        event_type: str,
        user_id: str,
        details: Dict[str, Any],
        prev_hash: str,
    ) -> str:
        payload = json.dumps(
            {
                "index": index,
                "timestamp": timestamp,
                "event_type": event_type,
                "user_id": user_id,
                "details": details,
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _read_entries(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        entries: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def log(
        self,
        event_type: str,
        user_id: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        entries = self._read_entries()
        index = len(entries)
        prev_hash = entries[-1]["hash"] if entries else GENESIS_HASH
        timestamp = datetime.utcnow().isoformat()
        details = details or {}

        digest = self._compute_hash(
            index, timestamp, event_type, user_id, details, prev_hash
        )
        event = AuditEvent(
            index=index,
            timestamp=timestamp,
            event_type=event_type,
            user_id=user_id,
            details=details,
            prev_hash=prev_hash,
            hash=digest,
        )

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), sort_keys=True) + "\n")
        return event

    def get_events(self) -> List[AuditEvent]:
        return [AuditEvent(**entry) for entry in self._read_entries()]

    def count(self) -> int:
        return len(self._read_entries())

    def verify_chain(self) -> bool:
        prev_hash = GENESIS_HASH
        for i, entry in enumerate(self._read_entries()):
            if entry["index"] != i or entry["prev_hash"] != prev_hash:
                return False
            expected = self._compute_hash(
                entry["index"],
                entry["timestamp"],
                entry["event_type"],
                entry["user_id"],
                entry["details"],
                entry["prev_hash"],
            )
            if expected != entry["hash"]:
                return False
            prev_hash = entry["hash"]
        return True

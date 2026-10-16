"""
Offline-first sync orchestration.

Polls the local queue, compresses (and optionally signs) a batch, uploads it
through an injected transport, then acknowledgements the records the server
accepted and folds any server records into a local snapshot via delta encoding.

Transport failures never raise: the queue is left untouched and the next
reconnection delay is returned from the exponential backoff policy. This keeps
the device fully autonomous while offline.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from src.sync.backoff import ExponentialBackoff
from src.sync.compression import (
    apply_delta,
    compute_delta,
    delta_to_bytes,
    records_by_id,
)
from src.sync.queue import SyncQueue
from src.sync.signing import sign_envelope


class SyncTransport(Protocol):
    """Minimal upload interface; implemented by the real mTLS client."""

    def upload(self, payload: bytes) -> bytes:
        ...


class OfflineError(RuntimeError):
    """Raised by transports when no connectivity is available."""


class NullTransport:
    """Transport that always fails, modelling a device with no network."""

    def upload(self, payload: bytes) -> bytes:
        raise OfflineError("no network connection")


@dataclass
class SyncResult:
    success: bool
    uploaded: int = 0
    synced_ids: List[str] = field(default_factory=list)
    server_records: List[Dict[str, Any]] = field(default_factory=list)
    retry_delay: Optional[float] = None
    error: Optional[str] = None


class SyncManager:
    def __init__(
        self,
        queue: SyncQueue,
        transport: SyncTransport,
        signing_key: Optional[bytes] = None,
        backoff: Optional[ExponentialBackoff] = None,
        max_batch: int = 50,
        server_snapshot: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        if max_batch <= 0:
            raise ValueError("max_batch must be positive")
        self.queue = queue
        self.transport = transport
        self.signing_key = signing_key
        self.backoff = backoff if backoff is not None else ExponentialBackoff()
        self.max_batch = max_batch
        self._server_snapshot: Dict[str, Dict[str, Any]] = dict(server_snapshot or {})

    def pending(self) -> int:
        return len(self.queue)

    def sync_once(self) -> SyncResult:
        batch = self.queue.peek(self.max_batch)
        if not batch:
            self.backoff.reset()
            return SyncResult(success=True)

        batch_by_id = records_by_id(batch)
        # The upload is a delta against what the server is already known to hold.
        known = {**self._server_snapshot, **batch_by_id}
        delta = compute_delta(self._server_snapshot, known)
        payload = delta_to_bytes(delta)
        if self.signing_key is not None:
            payload = sign_envelope(self.signing_key, payload)

        try:
            response_bytes = self.transport.upload(payload)
        except Exception as exc:  # noqa: BLE001 - offline must never crash the loop
            delay = self.backoff.next_delay()
            return SyncResult(
                success=False,
                uploaded=0,
                retry_delay=delay,
                error=str(exc),
            )

        response = self._parse_response(response_bytes)
        accepted = list(response.get("accepted", []))
        if not accepted:
            accepted = list(batch_by_id.keys())

        self.queue.ack(accepted)
        for record_id in accepted:
            if record_id in batch_by_id:
                self._server_snapshot[record_id] = batch_by_id[record_id]
        server_records = list(response.get("records", []))
        self._merge_server_records(server_records)
        self.backoff.reset()
        return SyncResult(
            success=True,
            uploaded=len(accepted),
            synced_ids=accepted,
            server_records=server_records,
        )

    def drain(self, max_batches: int = 100) -> List[SyncResult]:
        """Sync repeatedly until the queue is empty or a batch fails."""
        results: List[SyncResult] = []
        for _ in range(max_batches):
            if len(self.queue) == 0:
                break
            result = self.sync_once()
            results.append(result)
            if not result.success:
                break
        return results

    def server_snapshot(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._server_snapshot)

    def _merge_server_records(self, server_records: List[Dict[str, Any]]) -> None:
        if not server_records:
            return
        incoming = records_by_id(server_records)
        # Treat server records as upserts: only compute added/updated relative to
        # our snapshot, never infer deletions from an incremental list.
        known = {**self._server_snapshot, **incoming}
        delta = compute_delta(self._server_snapshot, known)
        self._server_snapshot = apply_delta(self._server_snapshot, delta)

    @staticmethod
    def _parse_response(response_bytes: bytes) -> Dict[str, Any]:
        if not response_bytes:
            return {}
        return json.loads(response_bytes.decode("utf-8"))

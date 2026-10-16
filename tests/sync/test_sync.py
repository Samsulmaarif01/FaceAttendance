"""Tests for the offline-first sync module (phase 4)."""

import json

import numpy as np
import pytest

from src.database.database import Database
from src.sync import (
    ExponentialBackoff,
    LWWElementSet,
    NullTransport,
    OfflineError,
    SyncManager,
    SyncQueue,
    apply_delta,
    compute_delta,
    delta_from_bytes,
    delta_to_bytes,
    generate_keypair,
    open_envelope,
    records_by_id,
    records_from_bytes,
    records_to_bytes,
    sign_envelope,
    sign_payload,
    verify_payload,
)
from src.sync.compression import compress, decompress


class TestCRDT:
    def test_add_update_remove(self):
        s = LWWElementSet().add("u1", {"id": "u1", "name": "Alice"}, 1.0)
        s = s.add("u1", {"id": "u1", "name": "Alice B"}, 2.0)
        assert s.contains("u1")
        assert s.get("u1") == {"id": "u1", "name": "Alice B"}

        s = s.remove("u1", 3.0)
        assert not s.contains("u1")
        assert s.get("u1") is None

    def test_remove_before_add_stays_present(self):
        s = LWWElementSet().remove("u1", 1.0).add("u1", {"id": "u1"}, 2.0)
        assert s.contains("u1")

    def test_merge_is_commutative_and_converges(self):
        a = LWWElementSet().add("u1", {"id": "u1", "v": 1}, 1.0)
        b = LWWElementSet().add("u2", {"id": "u2", "v": 2}, 2.0)
        assert a.merge(b).elements() == b.merge(a).elements()
        assert set(a.merge(b).keys()) == {"u1", "u2"}

    def test_merge_is_idempotent(self):
        a = LWWElementSet().add("u1", {"id": "u1"}, 1.0)
        b = LWWElementSet().add("u2", {"id": "u2"}, 2.0)
        merged = a.merge(b)
        assert merged.merge(merged).elements() == merged.elements()

    def test_concurrent_remove_wins_regardless_of_order(self):
        # add at t=1, remove at t=2 -> removed; merge order must not matter
        add = LWWElementSet().add("k", {"id": "k"}, 1.0)
        rem = LWWElementSet().remove("k", 2.0)
        assert not add.merge(rem).contains("k")
        assert not rem.merge(add).contains("k")

    def test_equal_timestamp_value_conflict_is_deterministic(self):
        a = LWWElementSet().add("k", {"id": "k", "v": "a"}, 5.0)
        b = LWWElementSet().add("k", {"id": "k", "v": "b"}, 5.0)
        assert a.merge(b).get("k") == b.merge(a).get("k")

    def test_serialization_round_trip(self):
        s = LWWElementSet().add("k", {"id": "k", "v": 1}, 1.0).remove("k2", 2.0)
        restored = LWWElementSet.from_dict(s.to_dict())
        assert restored.elements() == s.elements()
        assert restored.remove_set == s.remove_set


class TestBackoff:
    def test_deterministic_growth_and_cap(self):
        bo = ExponentialBackoff(base=1, factor=2, max_delay=10, jitter=False)
        assert [bo.next_delay() for _ in range(6)] == [1, 2, 4, 8, 10, 10]

    def test_reset_restarts_sequence(self):
        bo = ExponentialBackoff(base=2, factor=3, max_delay=100, jitter=False)
        bo.next_delay()
        bo.next_delay()
        bo.reset()
        assert bo.attempt == 0
        assert bo.next_delay() == 2

    def test_jitter_stays_within_bounds(self):
        bo = ExponentialBackoff(base=4, factor=2, max_delay=100, jitter=True, random_fn=lambda: 0.5)
        assert bo.next_delay() == 2.0  # raw 4 * 0.5

        low = ExponentialBackoff(base=4, factor=2, jitter=True, random_fn=lambda: 0.0)
        high = ExponentialBackoff(base=4, factor=2, jitter=True, random_fn=lambda: 0.999)
        assert low.next_delay() == 0.0
        assert high.next_delay() < 4.0

    def test_invalid_parameters(self):
        with pytest.raises(ValueError):
            ExponentialBackoff(base=0)
        with pytest.raises(ValueError):
            ExponentialBackoff(factor=0.5)
        with pytest.raises(ValueError):
            ExponentialBackoff(base=10, max_delay=5)


class TestCompression:
    def test_compress_round_trip(self):
        data = b"attendance" * 100
        assert decompress(compress(data)) == data

    def test_records_round_trip(self):
        records = [{"id": "a", "v": 1}, {"id": "b", "v": 2}]
        assert records_from_bytes(records_to_bytes(records)) == records

    def test_compute_and_apply_delta(self):
        previous = records_by_id([{"id": "a", "v": 1}, {"id": "b", "v": 2}])
        current = records_by_id([{"id": "a", "v": 9}, {"id": "c", "v": 3}])
        delta = compute_delta(previous, current)

        assert delta["deleted"] == ["b"]
        assert len(delta["added"]) == 1 and len(delta["updated"]) == 1
        assert apply_delta(previous, delta) == current

    def test_apply_delta_is_idempotent(self):
        previous = records_by_id([{"id": "a", "v": 1}])
        current = records_by_id([{"id": "a", "v": 2}, {"id": "b", "v": 3}])
        delta = compute_delta(previous, current)
        once = apply_delta(previous, delta)
        assert apply_delta(once, delta) == once

    def test_delta_serialization_round_trip(self):
        delta = {"added": [{"id": "x"}], "updated": [], "deleted": ["y"]}
        assert delta_from_bytes(delta_to_bytes(delta)) == delta


class TestSyncQueue:
    def test_enqueue_peek_ack(self):
        q = SyncQueue(max_size=5)
        assert q.enqueue({"id": "a"}) is True
        q.enqueue({"id": "b"})
        assert len(q) == 2
        assert [r["id"] for r in q.peek(1)] == ["a"]
        assert q.ack(["a"]) == 1
        assert len(q) == 1

    def test_update_existing_keeps_single_entry(self):
        q = SyncQueue(max_size=5)
        q.enqueue({"id": "a", "v": 1})
        q.enqueue({"id": "a", "v": 2})
        assert len(q) == 1
        assert q.peek()[0]["v"] == 2

    def test_backpressure_evict_oldest(self):
        q = SyncQueue(max_size=2, overflow_policy="evict_oldest")
        for i in range(4):
            q.enqueue({"id": f"r{i}"})
        assert len(q) == 2
        assert {r["id"] for r in q.peek()} == {"r2", "r3"}

    def test_backpressure_reject(self):
        q = SyncQueue(max_size=2, overflow_policy="reject")
        assert q.enqueue({"id": "a"}) is True
        assert q.enqueue({"id": "b"}) is True
        assert q.enqueue({"id": "c"}) is False
        assert len(q) == 2

    def test_persistence_round_trip(self, tmp_path):
        path = str(tmp_path / "queue.bin")
        q = SyncQueue(max_size=10, persist_path=path)
        q.enqueue({"id": "a", "v": 1})
        q.enqueue({"id": "b", "v": 2})

        reloaded = SyncQueue(max_size=10, persist_path=path)
        assert [r["id"] for r in reloaded.peek()] == ["a", "b"]

    def test_ack_persists(self, tmp_path):
        path = str(tmp_path / "queue.bin")
        q = SyncQueue(max_size=10, persist_path=path)
        q.enqueue({"id": "a"})
        q.ack(["a"])
        assert len(SyncQueue(max_size=10, persist_path=path)) == 0

    def test_invalid_config(self):
        with pytest.raises(ValueError):
            SyncQueue(max_size=0)
        with pytest.raises(ValueError):
            SyncQueue(overflow_policy="drop")

    def test_merge_converges_and_is_idempotent(self):
        a = SyncQueue(max_size=10)
        a.enqueue({"id": "x"}, timestamp=1.0)
        b = SyncQueue(max_size=10)
        b.enqueue({"id": "y"}, timestamp=2.0)

        merged_ab = SyncQueue(max_size=10).merge(a).merge(b)
        merged_ba = SyncQueue(max_size=10).merge(b).merge(a)
        assert {r["id"] for r in merged_ab.peek()} == {r["id"] for r in merged_ba.peek()} == {"x", "y"}
        assert merged_ab.merge(merged_ab).peek() == merged_ab.peek()

    def test_ack_creates_tombstone_and_compact_prunes(self, tmp_path):
        q = SyncQueue(max_size=4, persist_path=str(tmp_path / "q.bin"))
        q.enqueue({"id": "a"})
        q.ack(["a"])
        assert q.tombstones() >= 1
        assert len(q) == 0
        q.compact()
        assert q.tombstones() == 0

    def test_tombstone_does_not_come_back_after_reload(self, tmp_path):
        path = str(tmp_path / "q.bin")
        q = SyncQueue(max_size=4, persist_path=path)
        q.enqueue({"id": "a"})
        q.ack(["a"])
        reloaded = SyncQueue(max_size=4, persist_path=path)
        assert "a" not in reloaded
        assert len(reloaded) == 0

    def test_internal_order_field_is_not_exposed(self):
        q = SyncQueue(max_size=4)
        q.enqueue({"id": "a", "v": 1})
        assert "_queued_at" not in q.peek()[0]


def _accepted_from_payload(payload: bytes):
    delta = delta_from_bytes(payload)
    return [r["id"] for r in delta.get("added", [])] + [
        r["id"] for r in delta.get("updated", [])
    ]


class _FakeTransport:
    def __init__(self, response=None, fail=False):
        self.calls = []
        self.response = response
        self.fail = fail

    def upload(self, payload: bytes) -> bytes:
        self.calls.append(payload)
        if self.fail:
            raise OfflineError("offline")
        if self.response is not None:
            return self.response
        accepted = _accepted_from_payload(payload)
        return json.dumps({"accepted": accepted}).encode("utf-8")


class TestSyncManager:
    def test_success_acks_accepted_records(self):
        q = SyncQueue(max_size=10)
        q.enqueue({"id": "a"})
        q.enqueue({"id": "b"})
        manager = SyncManager(queue=q, transport=_FakeTransport(), max_batch=10)

        result = manager.sync_once()
        assert result.success is True
        assert result.uploaded == 2
        assert set(result.synced_ids) == {"a", "b"}
        assert len(q) == 0

    def test_empty_queue_is_noop(self):
        manager = SyncManager(queue=SyncQueue(), transport=_FakeTransport())
        result = manager.sync_once()
        assert result.success is True and result.uploaded == 0

    def test_server_records_merged_into_snapshot(self):
        response = json.dumps(
            {"accepted": ["a"], "records": [{"id": "s1", "v": 9}]}
        ).encode("utf-8")
        q = SyncQueue(max_size=10)
        q.enqueue({"id": "a"})
        manager = SyncManager(
            queue=q, transport=_FakeTransport(response=response), max_batch=10
        )
        manager.sync_once()
        snapshot = manager.server_snapshot()
        assert snapshot["s1"] == {"id": "s1", "v": 9}
        assert "a" in snapshot

    def test_offline_failure_keeps_queue_and_sets_backoff(self):
        q = SyncQueue(max_size=10)
        q.enqueue({"id": "a"})
        manager = SyncManager(queue=q, transport=_FakeTransport(fail=True))

        result = manager.sync_once()
        assert result.success is False
        assert result.retry_delay is not None
        assert len(q) == 1  # nothing lost while offline

    def test_drain_stops_on_failure(self):
        q = SyncQueue(max_size=10)
        q.enqueue({"id": "a"})
        manager = SyncManager(queue=q, transport=_FakeTransport(fail=True))
        results = manager.drain()
        assert len(results) == 1 and results[0].success is False

    def test_batch_respects_max_batch(self):
        q = SyncQueue(max_size=10)
        for i in range(5):
            q.enqueue({"id": f"r{i}"})
        manager = SyncManager(queue=q, transport=_FakeTransport(), max_batch=2)
        manager.sync_once()
        assert len(q) == 3

    def test_signed_payload_verifies(self):
        import base64

        private_pem, public_pem = generate_keypair()
        q = SyncQueue(max_size=10)
        q.enqueue({"id": "a"})
        transport = _FakeTransport()
        manager = SyncManager(
            queue=q, transport=transport, signing_key=private_pem, max_batch=10
        )
        manager.sync_once()

        envelope = json.loads(transport.calls[0].decode("utf-8"))
        payload = base64.b64decode(envelope["payload"])
        assert open_envelope(public_pem, transport.calls[0]) == payload

    def test_upload_payload_is_a_delta(self):
        q = SyncQueue(max_size=10)
        q.enqueue({"id": "a"})
        q.enqueue({"id": "b"})
        transport = _FakeTransport()
        SyncManager(queue=q, transport=transport, max_batch=10).sync_once()

        delta = delta_from_bytes(transport.calls[0])
        assert {r["id"] for r in delta["added"]} == {"a", "b"}
        assert delta["deleted"] == []

    def test_acked_records_are_not_resent(self):
        q = SyncQueue(max_size=10)
        q.enqueue({"id": "a"})
        transport = _FakeTransport()
        manager = SyncManager(queue=q, transport=transport, max_batch=10)
        manager.sync_once()

        q.enqueue({"id": "b"})
        manager.sync_once()
        delta = delta_from_bytes(transport.calls[1])
        assert {r["id"] for r in delta["added"]} == {"b"}


class TestSigning:
    def test_sign_and_verify(self):
        private_pem, public_pem = generate_keypair()
        payload = b"delta-payload"
        signature = sign_payload(private_pem, payload)
        assert verify_payload(public_pem, payload, signature) is True
        assert verify_payload(public_pem, b"tampered", signature) is False

    def test_envelope_round_trip(self):
        private_pem, public_pem = generate_keypair()
        envelope = sign_envelope(private_pem, b"hello")
        assert open_envelope(public_pem, envelope) == b"hello"

    def test_malformed_envelope_fails_safe(self):
        _, public_pem = generate_keypair()
        assert open_envelope(public_pem, b"not-json") is None
        assert open_envelope(public_pem, json.dumps({"payload": "!!"}).encode()) is None


class TestLocalAutonomy:
    def test_attendance_logging_and_queueing_work_offline(self, tmp_path):
        from cryptography.fernet import Fernet

        db = Database(
            db_path=str(tmp_path / "attendance.db"),
            encryption_key=Fernet.generate_key(),
            biohash_token=b"token",
        )
        queue = SyncQueue(max_size=10, persist_path=str(tmp_path / "queue.bin"))
        manager = SyncManager(queue=queue, transport=NullTransport())

        record_id = db.log_attendance("u1", similarity=0.9, liveness_score=0.8)
        queue.enqueue({
            "id": record_id,
            "user_id": "u1",
            "similarity": 0.9,
            "liveness_score": 0.8,
        })

        # Sync fails (no network) but local data is intact.
        result = manager.sync_once()
        assert result.success is False
        assert len(queue) == 1
        assert db.get_attendance_stats()["total"] == 1

    def test_null_transport_raises(self):
        with pytest.raises(OfflineError):
            NullTransport().upload(b"x")

    def test_database_enqueues_enrollment_events(self, tmp_path):
        from cryptography.fernet import Fernet

        queue = SyncQueue(max_size=10)
        db = Database(
            db_path=str(tmp_path / "attendance.db"),
            encryption_key=Fernet.generate_key(),
            biohash_token=b"token",
            sync_queue=queue,
        )
        embedding = np.random.randn(512).astype(np.float32)

        db.add_user("u1", "Alice", embedding)
        db.update_user_embedding("u1", embedding)
        db.delete_user("u1")

        event_types = [record["type"] for record in queue.peek()]
        assert event_types == ["user_enrolled", "template_updated", "user_deleted"]

    def test_database_without_sync_queue_is_unaffected(self, tmp_path):
        from cryptography.fernet import Fernet

        db = Database(
            db_path=str(tmp_path / "attendance.db"),
            encryption_key=Fernet.generate_key(),
            biohash_token=b"token",
        )
        assert db.sync_queue is None
        embedding = np.ones(512, dtype=np.float32)
        assert db.add_user("u1", "Alice", embedding) is True

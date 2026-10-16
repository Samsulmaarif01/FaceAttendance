"""Tests for the local web API (phase 6)."""

import cv2
import numpy as np
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.pipeline import create_demo_config


def _jpg(seed: int, size=(480, 640)) -> bytes:
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (size[0], size[1], 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


@pytest.fixture
def client(tmp_path):
    config = create_demo_config(
        detector_backend="dummy",
        database_path=str(tmp_path / "test.db"),
        audit_log_path=str(tmp_path / "audit.log"),
        database_encryption_key=Fernet.generate_key(),
        audit_enabled=False,
    )
    return TestClient(create_app(config))


def _files(seed: int):
    return {"file": ("frame.jpg", _jpg(seed), "image/jpeg")}


class TestHealth:
    def test_reports_demo_mode(self, client):
        data = client.get("/api/health").json()
        assert data["status"] == "ok"
        assert data["demo_mode"] is True
        assert data["recognition_models"] == 1
        assert data["matcher_backend"] == "linear"


class TestRecognize:
    def test_no_match_on_empty_database(self, client):
        res = client.post("/api/recognize", files=_files(1))
        assert res.status_code == 200
        body = res.json()
        assert body["count"] == 1
        assert body["faces"][0]["match"] is None
        assert body["faces"][0]["liveness"]["is_live"] is True

    def test_invalid_image_is_rejected(self, client):
        res = client.post("/api/recognize", files={"file": ("x.jpg", b"not-an-image", "image/jpeg")})
        assert res.status_code == 400

    def test_enroll_then_recognize_round_trip(self, client):
        enroll = client.post("/api/enroll", data={"name": "Alice"}, files=_files(2))
        assert enroll.status_code == 200
        user_id = enroll.json()["user_id"]

        res = client.post("/api/recognize", files=_files(2))
        match = res.json()["faces"][0]["match"]
        assert match is not None
        assert match["matched"] is True
        assert match["user_id"] == user_id
        assert match["name"] == "Alice"
        assert match["similarity"] > 0.9


class TestEnroll:
    def test_enroll_assigns_id_and_lists_user(self, client):
        res = client.post("/api/enroll", data={"name": "Bob", "user_id": "b1"}, files=_files(3))
        assert res.status_code == 200
        assert res.json() == {
            "success": True,
            "user_id": "b1",
            "name": "Bob",
            "embedding_dim": 512,
        }
        users = client.get("/api/users").json()
        assert users["count"] == 1
        assert users["users"][0]["id"] == "b1"

    def test_duplicate_enroll_conflicts(self, client):
        client.post("/api/enroll", data={"name": "Bob", "user_id": "b1"}, files=_files(4))
        res = client.post("/api/enroll", data={"name": "Bob", "user_id": "b1"}, files=_files(4))
        assert res.status_code == 409

    def test_missing_name_is_validation_error(self, client):
        res = client.post("/api/enroll", files=_files(5))
        assert res.status_code == 422


class TestAttendanceAndStats:
    def test_matched_recognition_logs_attendance(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        res = client.post("/api/recognize", files=_files(6))
        assert res.json()["faces"][0]["attendance_logged"] is True

        stats = client.get("/api/stats").json()
        assert stats["total"] == 1
        assert stats["users"] == 1

        records = client.get("/api/attendance").json()
        assert records["count"] == 1
        assert records["records"][0]["user_id"] == "a1"

    def test_recognize_without_log_writes_nothing(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        res = client.post("/api/recognize?log=false", files=_files(6))
        assert res.status_code == 200
        assert res.json()["faces"][0]["match"]["matched"] is True
        assert res.json()["faces"][0]["attendance_logged"] is False
        assert client.get("/api/stats").json()["total"] == 0

    def test_attendance_is_throttled_per_user(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        assert client.post("/api/recognize", files=_files(6)).json()["faces"][0]["attendance_logged"] is True
        assert client.post("/api/recognize", files=_files(6)).json()["faces"][0]["attendance_logged"] is False
        assert client.get("/api/stats").json()["total"] == 1

    def test_users_report_last_attendance(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        client.post("/api/recognize", files=_files(6))
        user = client.get("/api/users").json()["users"][0]
        assert user["attendance_count"] == 1
        assert user["last_attendance"] is not None


class TestAttendanceManagement:
    def test_clear_attendance(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(7))
        client.post("/api/recognize", files=_files(7))
        assert client.get("/api/stats").json()["total"] == 1

        res = client.delete("/api/attendance")
        assert res.status_code == 200
        assert res.json()["deleted"] == 1
        assert client.get("/api/stats").json()["total"] == 0

    def test_delete_user(self, client):
        client.post("/api/enroll", data={"name": "Bob", "user_id": "b1"}, files=_files(8))
        res = client.delete("/api/users/b1")
        assert res.status_code == 200
        assert res.json() == {"success": True, "id": "b1", "deleted": None}
        assert client.get("/api/users").json()["count"] == 0

    def test_delete_missing_user_is_404(self, client):
        assert client.delete("/api/users/nope").status_code == 404


class TestSyncAndDashboard:
    def test_sync_disabled_when_not_configured(self, client):
        res = client.post("/api/sync")
        assert res.status_code == 200
        assert res.json()["status"] == "disabled"

    def test_dashboard_and_assets_are_served(self, client):
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/style.css").status_code == 200

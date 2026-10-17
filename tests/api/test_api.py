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
        body = res.json()
        assert body["success"] is True
        assert body["user_id"] == "b1"
        assert body["name"] == "Bob"
        assert body["embedding_dim"] == 512
        assert body["duplicate"] is False
        users = client.get("/api/users").json()
        assert users["count"] == 1
        assert users["users"][0]["id"] == "b1"

    def test_conflicting_user_id_with_a_different_face_is_409(self, client):
        """user_id yang sama tapi wajah BERBEDA tetap ditolak (409) —
        mencegah template orang lain tertimpa."""
        client.post("/api/enroll", data={"name": "Bob", "user_id": "b1"}, files=_files(4))
        res = client.post("/api/enroll", data={"name": "Bob", "user_id": "b1"}, files=_files(28))
        assert res.status_code == 409

    def test_missing_name_is_rejected_after_face_check(self, client):
        """Nama boleh kosong saat unggah (backend cek wajah dulu), tapi wajah baru
        tanpa nama harus ditolak dengan pesan yang jelas."""
        res = client.post("/api/enroll", data={"name": ""}, files=_files(5))
        assert res.status_code == 400
        assert "nama" in res.json()["detail"].lower()
        # tidak boleh ada user yang tersimpan tanpa nama
        assert client.get("/api/users").json()["count"] == 0


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


class TestEnrollDuplicates:
    """Daftar dari gambar /Daftarkan wajah hanya untuk mendaftarkan wajah, dan
    tidak boleh membuat pengguna ganda untuk wajah yang sama."""

    def test_same_face_twice_does_not_create_second_user(self, client):
        r1 = client.post("/api/enroll", data={"name": "Samsul Maarif"}, files=_files(21))
        assert r1.status_code == 200 and r1.json()["success"] is True

        r2 = client.post("/api/enroll", data={"name": "Samsul Maarif (lagi)"}, files=_files(21))
        assert r2.status_code == 200
        body = r2.json()
        assert body["success"] is False
        assert body["duplicate"] is True
        assert body["existing_user_id"] == r1.json()["user_id"]
        assert body["existing_name"] == "Samsul Maarif"
        assert body["similarity"] > 0.9
        # tidak ada pengguna baru
        assert client.get("/api/users").json()["count"] == 1

    def test_reenroll_same_user_id_refreshes_template(self, client):
        first = client.post("/api/enroll", data={"name": "Samsul", "user_id": "s1"}, files=_files(22)).json()
        again = client.post("/api/enroll", data={"name": "Samsul", "user_id": "s1"}, files=_files(22)).json()
        assert again["success"] is True
        assert again["updated"] is True
        assert again["duplicate"] is True          # wajah memang yang sama
        assert again["existing_user_id"] == "s1"
        assert client.get("/api/users").json()["count"] == 1
        assert first["user_id"] == "s1"

    def test_known_face_as_different_user_id_is_refused(self, client):
        client.post("/api/enroll", data={"name": "Samsul", "user_id": "s1"}, files=_files(23))
        r = client.post("/api/enroll", data={"name": "Orang lain", "user_id": "s2"}, files=_files(23))
        assert r.status_code == 200
        body = r.json()
        assert body["duplicate"] is True
        assert body["existing_user_id"] == "s1"
        assert client.get("/api/users").json()["count"] == 1

    def test_enroll_new_face_without_name_is_rejected(self, client):
        r = client.post("/api/enroll", data={"name": ""}, files=_files(24))
        assert r.status_code == 400
        assert "nama" in r.json()["detail"].lower()

    def test_enrollment_never_writes_attendance(self, client):
        client.post("/api/enroll", data={"name": "Samsul", "user_id": "s1"}, files=_files(25))
        assert client.get("/api/stats").json()["total"] == 0


class TestDeletedUserRecovery:
    """User dihapus = soft delete; riwayat & template harus tetap bisa dipulihkan."""

    def test_attendance_keeps_name_after_user_deleted(self, client):
        client.post("/api/enroll", data={"name": "Samsul Maarif", "user_id": "s1"}, files=_files(26))
        client.post("/api/recognize?direction=in", files=_files(26))
        assert client.delete("/api/users/s1").json()["success"] is True

        records = client.get("/api/attendance").json()["records"]
        assert len(records) == 1
        # riwayat milik user terhapus tetap menampilkan nama, bukan "—"
        assert records[0]["name"] == "Samsul Maarif"

    def test_reenroll_deleted_face_reactivates_and_keeps_history(self, client):
        client.post("/api/enroll", data={"name": "Samsul Maarif", "user_id": "s1"}, files=_files(27))
        client.post("/api/recognize?direction=in", files=_files(27))
        client.delete("/api/users/s1")

        r = client.post("/api/enroll", data={"name": "Samsul Maarif"}, files=_files(27))
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["reactivated"] is True
        assert body["user_id"] == "s1", "harus memakai user_id yang sama"

        users = client.get("/api/users").json()
        assert users["count"] == 1, "tidak boleh membuat pengguna kedua"
        # riwayat lama tetap menempel ke user yang diaktifkan kembali
        assert client.get("/api/users").json()["users"][0]["attendance_count"] == 1


    def test_reenroll_deleted_face_reactivates_even_with_other_user_id(self, client):
        """Semua user non-aktif + kolom User ID terisi id LAIN.

        Harus mengaktifkan kembali, bukan menjawab "sudah terdaftar" — kalau
        tidak, Data Karyawan tetap kosong dan wajahnya tidak akan bisa absen.
        """
        client.post("/api/enroll", data={"name": "Samsul Maarif", "user_id": "s1"}, files=_files(31))
        client.delete("/api/users/s1")
        assert client.get("/api/users").json()["count"] == 0

        r = client.post("/api/enroll", data={"name": "Samsul", "user_id": "Id001"}, files=_files(31))
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["reactivated"] is True, "user non-aktif harus diaktifkan kembali"
        assert body["user_id"] == "s1"

        users = client.get("/api/users").json()
        assert users["count"] == 1, "harus ada tepat satu user aktif"
        assert users["users"][0]["id"] == "s1"

    def test_reenroll_deleted_face_then_can_attend(self, client):
        """Setelah diaktifkan kembali, wajahnya harus bisa absen lagi."""
        client.post("/api/enroll", data={"name": "Samsul Maarif", "user_id": "s1"}, files=_files(32))
        client.delete("/api/users/s1")
        client.post("/api/enroll", data={"name": "Samsul Maarif"}, files=_files(32))

        face = client.post("/api/recognize?direction=in", files=_files(32)).json()["faces"][0]
        assert face["match"] is not None and face["match"]["matched"] is True
        assert face["attendance_logged"] is True


class TestDeleteModes:
    """Admin punya dua pilihan: arsipkan (soft delete) atau hapus permanen."""

    def test_archive_is_the_default_and_keeps_history(self, client):
        client.post("/api/enroll", data={"name": "Samsul", "user_id": "s1"}, files=_files(40))
        client.post("/api/recognize?direction=in", files=_files(40))
        client.post("/api/recognize?direction=out", files=_files(40))
        assert client.get("/api/stats").json()["total"] == 2

        res = client.delete("/api/users/s1")
        assert res.status_code == 200
        assert res.json()["mode"] == "archived"
        # user hilang dari daftar aktif, tapi riwayat tetap ada
        assert client.get("/api/users").json()["count"] == 0
        records = client.get("/api/attendance").json()["records"]
        assert len(records) == 2
        assert records[0]["name"] == "Samsul"

    def test_archived_user_can_be_listed_and_restored(self, client):
        client.post("/api/enroll", data={"name": "Samsul", "user_id": "s1"}, files=_files(41))
        client.post("/api/recognize?direction=in", files=_files(41))
        client.delete("/api/users/s1")

        listed = client.get("/api/users?include_archived=true").json()
        assert listed["count"] == 1
        assert listed["users"][0]["is_archived"] is True
        assert listed["users"][0]["attendance_count"] == 1

        res = client.post("/api/users/s1/restore")
        assert res.status_code == 200
        assert res.json()["mode"] == "restored"
        assert client.get("/api/users").json()["count"] == 1
        assert client.get("/api/users").json()["users"][0]["is_archived"] is False

    def test_permanent_delete_removes_user_and_their_attendance(self, client):
        client.post("/api/enroll", data={"name": "Samsul", "user_id": "s1"}, files=_files(42))
        client.post("/api/recognize?direction=in", files=_files(42))
        client.post("/api/recognize?direction=out", files=_files(42))

        res = client.delete("/api/users/s1?permanent=true")
        assert res.status_code == 200
        assert res.json()["mode"] == "permanent"
        assert res.json()["attendance_deleted"] == 2
        assert client.get("/api/users?include_archived=true").json()["count"] == 0
        assert client.get("/api/stats").json()["total"] == 0

    def test_permanent_delete_frees_the_face_for_a_clean_reenroll(self, client):
        """Setelah hapus permanen, template hilang -> wajah yang sama boleh
        didaftarkan lagi sebagai user BARU (bukan dianggap duplikat)."""
        client.post("/api/enroll", data={"name": "Samsul", "user_id": "s1"}, files=_files(43))
        client.delete("/api/users/s1")
        # arsip dulu -> masih terdeteksi duplikat dan diaktifkan kembali
        again = client.post("/api/enroll", data={"name": "Samsul", "user_id": "s2"}, files=_files(43)).json()
        assert again["reactivated"] is True

        client.delete("/api/users/s1?permanent=true")
        fresh = client.post("/api/enroll", data={"name": "Samsul Baru", "user_id": "s3"}, files=_files(43)).json()
        assert fresh["success"] is True
        assert not fresh.get("duplicate")
        assert fresh["user_id"] == "s3"

    def test_restore_missing_user_is_404(self, client):
        assert client.post("/api/users/nope/restore").status_code == 404

    def test_permanent_delete_missing_user_is_404(self, client):
        assert client.delete("/api/users/nope?permanent=true").status_code == 404


class TestAttendanceDirection:
    def test_checkout_without_checkin_is_blocked(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        face = client.post("/api/recognize?direction=out", files=_files(6)).json()["faces"][0]
        assert face["match"]["matched"] is True
        assert face["attendance_logged"] is False
        assert face["attendance_status"] == "not_checked_in"
        assert client.get("/api/stats").json()["total"] == 0

    def test_checkin_then_checkout_records_both(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        assert client.post("/api/recognize?direction=in", files=_files(6)).json()["faces"][0]["attendance_status"] == "logged"
        assert client.post("/api/recognize?direction=out", files=_files(6)).json()["faces"][0]["attendance_status"] == "logged"
        records = client.get("/api/attendance").json()["records"]
        assert sorted(r["direction"] for r in records) == ["in", "out"]
        assert client.get("/api/stats").json()["total"] == 2

    def test_repeat_direction_same_day_is_duplicate(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        client.post("/api/recognize?direction=in", files=_files(6))
        face = client.post("/api/recognize?direction=in", files=_files(6)).json()["faces"][0]
        assert face["attendance_logged"] is False
        assert face["attendance_status"] == "duplicate"
        assert face["attendance_duplicate_at"] is not None
        assert client.get("/api/stats").json()["total"] == 1

    def test_recheckin_is_allowed_after_checkout(self, client):
        """masuk -> pulang -> masuk: after checking out the user may check in again."""
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        assert client.post("/api/recognize?direction=in", files=_files(6)).json()["faces"][0]["attendance_status"] == "logged"
        assert client.post("/api/recognize?direction=out", files=_files(6)).json()["faces"][0]["attendance_status"] == "logged"

        face = client.post("/api/recognize?direction=in", files=_files(6)).json()["faces"][0]
        assert face["attendance_logged"] is True
        assert face["attendance_status"] == "logged"

        records = client.get("/api/attendance").json()["records"]
        assert [r["direction"] for r in records] == ["in", "out", "in"]
        assert client.get("/api/stats").json()["total"] == 3

    def test_second_checkout_is_duplicate(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        client.post("/api/recognize?direction=in", files=_files(6))
        client.post("/api/recognize?direction=out", files=_files(6))
        face = client.post("/api/recognize?direction=out", files=_files(6)).json()["faces"][0]
        assert face["attendance_logged"] is False
        assert face["attendance_status"] == "duplicate"
        assert client.get("/api/stats").json()["total"] == 2

    def test_checkin_while_still_checked_in_is_duplicate(self, client):
        """A second 'masuk' while the first is still open stays a duplicate."""
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        client.post("/api/recognize?direction=in", files=_files(6))
        face = client.post("/api/recognize?direction=in", files=_files(6)).json()["faces"][0]
        assert face["attendance_status"] == "duplicate"


class TestGateMode:
    """Gate (IoT) access: a recognised face is always let through."""

    def test_gate_grants_access_on_checkin(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        face = client.post("/api/recognize?direction=in&gate=true", files=_files(6)).json()["faces"][0]
        assert face["match"]["matched"] is True
        assert face["gate_granted"] is True

    def test_gate_records_checkout_without_checkin(self, client):
        """Leaving must never be blocked by the attendance pairing rule."""
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        face = client.post("/api/recognize?direction=out&gate=true", files=_files(6)).json()["faces"][0]
        assert face["gate_granted"] is True
        assert face["attendance_logged"] is True
        assert face["attendance_status"] == "logged"
        records = client.get("/api/attendance").json()["records"]
        assert [r["direction"] for r in records] == ["out"]

    def test_attendance_mode_still_blocks_checkout_without_checkin(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        face = client.post("/api/recognize?direction=out", files=_files(6)).json()["faces"][0]
        assert face["gate_granted"] is False
        assert face["attendance_status"] == "not_checked_in"
        assert client.get("/api/stats").json()["total"] == 0

    def test_gate_grants_access_even_when_attendance_is_duplicate(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        client.post("/api/recognize?direction=in&gate=true", files=_files(6))
        face = client.post("/api/recognize?direction=in&gate=true", files=_files(6)).json()["faces"][0]
        assert face["attendance_status"] == "duplicate"   # not recorded twice
        assert face["gate_granted"] is True                # but access still granted
        assert client.get("/api/stats").json()["total"] == 1

    def test_gate_does_not_grant_for_unknown_face(self, client):
        face = client.post("/api/recognize?direction=in&gate=true", files=_files(9)).json()["faces"][0]
        assert face["match"] is None
        assert face["gate_granted"] is False

    def test_invalid_direction_is_rejected(self, client):
        assert client.post("/api/recognize?direction=sideways", files=_files(6)).status_code == 400

    def test_users_report_today_status(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(6))
        assert client.get("/api/users").json()["users"][0]["checked_in_today"] is False
        client.post("/api/recognize?direction=in", files=_files(6))
        user = client.get("/api/users").json()["users"][0]
        assert user["checked_in_today"] is True
        assert user["checked_out_today"] is False


class TestAttendanceManagement:
    def test_clear_attendance(self, client):
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(7))
        client.post("/api/recognize", files=_files(7))
        assert client.get("/api/stats").json()["total"] == 1

        res = client.delete("/api/attendance")
        assert res.status_code == 200
        assert res.json()["deleted"] == 1
        assert client.get("/api/stats").json()["total"] == 0

    def test_attendance_can_be_re_logged_immediately_after_clear(self, client):
        """Clearing the history must not leave the in-memory throttle blocking
        the next attendance (it used to report "already recorded" instead)."""
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(7))
        assert client.post("/api/recognize", files=_files(7)).json()["faces"][0]["attendance_logged"] is True

        client.delete("/api/attendance")

        face = client.post("/api/recognize", files=_files(7)).json()["faces"][0]
        assert face["attendance_logged"] is True
        assert face["attendance_status"] == "logged"
        assert client.get("/api/stats").json()["total"] == 1
        assert client.get("/api/attendance").json()["records"][0]["direction"] == "in"

    def test_checkout_can_be_logged_immediately_after_clear(self, client):
        """Same regression for the 'out' direction."""
        client.post("/api/enroll", data={"name": "Alice", "user_id": "a1"}, files=_files(7))
        client.post("/api/recognize?direction=in", files=_files(7))
        assert client.post("/api/recognize?direction=out", files=_files(7)).json()["faces"][0]["attendance_logged"] is True

        client.delete("/api/attendance")

        face = client.post("/api/recognize?direction=out", files=_files(7)).json()["faces"][0]
        assert face["attendance_status"] == "not_checked_in"  # no check-in exists any more

        face = client.post("/api/recognize?direction=in", files=_files(7)).json()["faces"][0]
        assert face["attendance_logged"] is True
        face = client.post("/api/recognize?direction=out", files=_files(7)).json()["faces"][0]
        assert face["attendance_logged"] is True
        assert client.get("/api/stats").json()["total"] == 2

    def test_delete_user(self, client):
        client.post("/api/enroll", data={"name": "Bob", "user_id": "b1"}, files=_files(8))
        res = client.delete("/api/users/b1")
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["id"] == "b1"
        assert res.json()["mode"] == "archived"   # default = arsip, bukan hapus permanen
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

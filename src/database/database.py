"""
Database module with encrypted SQLite and biohashing for template protection.
"""

import os
import sqlite3
import hashlib
import secrets
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timedelta
from contextlib import contextmanager
import json

import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

from src.security.keystore import FileKeyStore, KeyStore
from src.security.audit import AuditLog

if TYPE_CHECKING:
    from src.sync.queue import SyncQueue


@dataclass
class User:
    id: str
    name: str
    biohashed_template: bytes  # Biohashed embedding
    salt: bytes
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


@dataclass
class AttendanceRecord:
    id: str
    user_id: str
    timestamp: datetime
    similarity: float
    liveness_score: float
    synced: bool = False
    device_id: str = ""
    direction: str = "in"  # "in" (masuk) or "out" (pulang)
    name: Optional[str] = None  # resolved from users, kept even if user was deleted


class BioHasher:
    def __init__(self, token_length: int = 32, iterations: int = 1000):
        self.token_length = token_length
        self.iterations = iterations

    def generate_salt(self) -> bytes:
        return secrets.token_bytes(16)

    def biohash(self, embedding: np.ndarray, token: bytes, salt: bytes) -> bytes:
        """
        Cancelable biometrics: biohash = hash(embedding || token || salt)
        The token is device-specific and stored in TPM/secure element.
        """
        # Normalize embedding to bytes
        emb_bytes = embedding.astype(np.float32).tobytes()
        data = emb_bytes + token + salt

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.token_length,
            salt=salt,
            iterations=self.iterations,
        )
        return kdf.derive(data)

    def verify(self, embedding: np.ndarray, stored_hash: bytes, token: bytes, salt: bytes) -> bool:
        computed = self.biohash(embedding, token, salt)
        return secrets.compare_digest(computed, stored_hash)


class Database:
    def __init__(
        self,
        db_path: str = "data/attendance.db",
        encryption_key: Optional[bytes] = None,
        biohash_token: Optional[bytes] = None,
        audit_log: Optional[AuditLog] = None,
        sync_queue: Optional["SyncQueue"] = None,
    ):
        self.db_path = db_path
        self.encryption_key = encryption_key or self._get_or_create_key()
        self.cipher = Fernet(self.encryption_key)
        self.biohash_token = biohash_token or secrets.token_bytes(32)
        self.biohasher = BioHasher()
        self.audit_log = audit_log
        self.sync_queue = sync_queue
        self.unreadable_templates: List[str] = []
        self._init_db()

    def _audit(self, event_type: str, user_id: str = "", details: Optional[dict] = None) -> None:
        if self.audit_log is not None:
            self.audit_log.log(event_type, user_id=user_id, details=details or {})

    def _enqueue_sync(self, event: dict) -> None:
        """Queue a local event for sync (no-op when sync is disabled)."""
        if self.sync_queue is not None:
            self.sync_queue.enqueue(event)

    def _get_or_create_key(self) -> bytes:
        return KeyStore(FileKeyStore("data/db.key")).get_or_create_key()

    def _encrypt_embedding(self, embedding: np.ndarray) -> bytes:
        return self.cipher.encrypt(embedding.astype(np.float32).tobytes())

    def _decrypt_embedding(self, blob: bytes) -> np.ndarray:
        raw = self.cipher.decrypt(blob)
        return np.frombuffer(raw, dtype=np.float32).copy()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    biohashed_template BLOB NOT NULL,
                    salt BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    encrypted_embedding BLOB,
                    photo BLOB
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    similarity REAL NOT NULL,
                    liveness_score REAL NOT NULL,
                    synced INTEGER DEFAULT 0,
                    device_id TEXT DEFAULT '',
                    direction TEXT DEFAULT 'in',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_attendance_user_time
                ON attendance(user_id, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_attendance_synced
                ON attendance(synced)
            """)
            # Migration: older databases lack the encrypted embedding column.
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
            if "encrypted_embedding" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN encrypted_embedding BLOB")
            # Migration: user photo (avatar thumbnail) column.
            if "photo" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN photo BLOB")
            # Migration: older attendance tables lack the direction column.
            att_columns = [row["name"] for row in conn.execute("PRAGMA table_info(attendance)").fetchall()]
            if "direction" not in att_columns:
                conn.execute("ALTER TABLE attendance ADD COLUMN direction TEXT DEFAULT 'in'")
            conn.commit()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def add_user(self, user_id: str, name: str, embedding: np.ndarray, photo: Optional[bytes] = None) -> bool:
        salt = self.biohasher.generate_salt()
        biohashed = self.biohasher.biohash(embedding, self.biohash_token, salt)
        encrypted = self._encrypt_embedding(embedding)
        now = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO users
                           (id, name, biohashed_template, salt, created_at, updated_at, encrypted_embedding, photo)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, name, biohashed, salt, now, now, encrypted, photo),
                )
                conn.commit()
                self._audit("user_enrolled", user_id, {"name": name})
                self._enqueue_sync({
                    "id": secrets.token_urlsafe(16),
                    "type": "user_enrolled",
                    "user_id": user_id,
                    "name": name,
                    "timestamp": now,
                })
                return True
            except sqlite3.IntegrityError:
                self._audit("user_enrollment_rejected", user_id, {"name": name, "reason": "duplicate"})
                return False

    def update_user_photo(self, user_id: str, photo: bytes) -> bool:
        """Set (or replace) the user's avatar thumbnail."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE users SET photo = ?, updated_at = ? WHERE id = ?",
                (photo, datetime.utcnow().isoformat(), user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_user_photo(self, user_id: str) -> Optional[bytes]:
        """Return the user's avatar JPEG bytes, or None when not stored."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT photo FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None or row["photo"] is None:
            return None
        return bytes(row["photo"])

    def get_user(self, user_id: str) -> Optional[User]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return User(
                    id=row["id"],
                    name=row["name"],
                    biohashed_template=row["biohashed_template"],
                    salt=row["salt"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    is_active=bool(row["is_active"]),
                )
        return None

    def get_all_users(self, include_archived: bool = False) -> List[User]:
        query = "SELECT * FROM users"
        if not include_archived:
            query += " WHERE is_active = 1"
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
            return [
                User(
                    id=r["id"],
                    name=r["name"],
                    biohashed_template=r["biohashed_template"],
                    salt=r["salt"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                    is_active=bool(r["is_active"]),
                )
                for r in rows
            ]

    def update_user_embedding(self, user_id: str, embedding: np.ndarray) -> bool:
        salt = self.biohasher.generate_salt()
        biohashed = self.biohasher.biohash(embedding, self.biohash_token, salt)
        encrypted = self._encrypt_embedding(embedding)
        now = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            cur = conn.execute(
                """UPDATE users SET biohashed_template = ?, salt = ?, updated_at = ?,
                       encrypted_embedding = ?
                   WHERE id = ?""",
                (biohashed, salt, now, encrypted, user_id),
            )
            conn.commit()
            if cur.rowcount > 0:
                self._audit("template_updated", user_id)
                self._enqueue_sync({
                    "id": secrets.token_urlsafe(16),
                    "type": "template_updated",
                    "user_id": user_id,
                    "timestamp": now,
                })
            return cur.rowcount > 0

    def delete_user(self, user_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
            conn.commit()
            if cur.rowcount > 0:
                self._audit("user_deleted", user_id)
                self._enqueue_sync({
                    "id": secrets.token_urlsafe(16),
                    "type": "user_deleted",
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            return cur.rowcount > 0

    def reactivate_user(
        self,
        user_id: str,
        embedding: Optional[np.ndarray] = None,
        name: Optional[str] = None,
    ) -> bool:
        """
        Re-enable a soft-deleted user, keeping their attendance history.

        Used when the same face is enrolled again after the owner was deleted:
        the original row (and therefore every record it owns) is restored
        instead of creating a duplicate user that would orphan the history.
        """
        with self._get_conn() as conn:
            if name:
                conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
            cur = conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
            conn.commit()
            reactivated = cur.rowcount > 0
        if not reactivated:
            return False
        if embedding is not None:
            self.update_user_embedding(user_id, embedding)
        self._audit("user_reactivated", user_id, {"name": name} if name else {})
        self._enqueue_sync({
            "id": secrets.token_urlsafe(16),
            "type": "user_reactivated",
            "user_id": user_id,
            "name": name or "",
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True

    def hard_delete_user(self, user_id: str) -> Tuple[bool, int]:
        """
        Permanently delete a user AND every attendance record they own.

        Unlike :meth:`delete_user` (soft delete / archive) this leaves nothing
        behind: the row and its Fernet-encrypted template are gone, so the face
        can no longer be recognised as "already registered" and re-enrolling it
        produces a genuinely new user. Returns (deleted, attendance_deleted).
        """
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM attendance WHERE user_id = ?", (user_id,))
            attendance_deleted = cur.rowcount
            cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            deleted = cur.rowcount > 0
        if deleted:
            self._audit("user_hard_deleted", user_id, {"attendance_deleted": attendance_deleted})
            self._enqueue_sync({
                "id": secrets.token_urlsafe(16),
                "type": "user_hard_deleted",
                "user_id": user_id,
                "attendance_deleted": attendance_deleted,
                "timestamp": datetime.utcnow().isoformat(),
            })
        return deleted, attendance_deleted

    def restore_user(self, user_id: str) -> bool:
        """Bring an archived (soft-deleted) user back, template untouched."""
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
            conn.commit()
            restored = cur.rowcount > 0
        if restored:
            self._audit("user_restored", user_id)
            self._enqueue_sync({
                "id": secrets.token_urlsafe(16),
                "type": "user_restored",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
        return restored

    def verify_user(self, user_id: str, embedding: np.ndarray) -> bool:
        user = self.get_user(user_id)
        if not user:
            self._audit("verification_failed", user_id)
            return False
        verified = self.biohasher.verify(embedding, user.biohashed_template, self.biohash_token, user.salt)
        if not verified:
            self._audit("verification_failed", user_id)
        return verified

    def get_user_templates(self, include_inactive: bool = False) -> Dict[str, np.ndarray]:
        """
        Return user_id -> decrypted embedding for active users.

        Embeddings are stored Fernet-encrypted at rest (separate from the
        biohashed template) so that 1:N matching is possible; they are only
        decrypted in memory. The biohashed template remains the primary record
        for 1:1 verification.

        ``include_inactive=True`` also returns soft-deleted users. Enrollment
        uses that so a face whose owner was deleted is recognised as "the same
        person" instead of silently creating a second user.
        """
        templates: Dict[str, np.ndarray] = {}
        query = """SELECT id, encrypted_embedding FROM users
                   WHERE encrypted_embedding IS NOT NULL"""
        if not include_inactive:
            query += " AND is_active = 1"
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
        # Dekripsi yang gagal DIJAGA, bukan ditelan diam-diam: kalau kunci
        # Fernet berubah (mis. data/db.key terhapus/terganti) semua template jadi
        # sampah dan setiap scan akan melaporkan "wajah belum terdaftar" padahal
        # user-nya ada. surfaced lewat /api/health.
        unreadable: List[str] = []
        for row in rows:
            try:
                templates[row["id"]] = self._decrypt_embedding(row["encrypted_embedding"])
            except Exception:
                unreadable.append(row["id"])
        self.unreadable_templates = unreadable
        if unreadable:
            print(
                f"WARNING: {len(unreadable)} face template(s) could not be decrypted "
                f"(wrong/missing encryption key?): {', '.join(unreadable[:5])}"
                f"{' ...' if len(unreadable) > 5 else ''}"
            )
        return templates

    def log_attendance(
        self,
        user_id: str,
        similarity: float,
        liveness_score: float,
        device_id: str = "",
        direction: str = "in",
    ) -> str:
        record_id = secrets.token_urlsafe(16)
        timestamp = datetime.utcnow().isoformat()
        direction = "out" if str(direction).lower() in ("out", "pulang") else "in"

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO attendance
                       (id, user_id, timestamp, similarity, liveness_score, device_id, direction)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (record_id, user_id, timestamp, similarity, liveness_score, device_id, direction),
            )
            conn.commit()
        self._audit(
            "attendance_logged",
            user_id,
            {
                "similarity": similarity,
                "liveness_score": liveness_score,
                "device_id": device_id,
                "direction": direction,
            },
        )
        return record_id

    @staticmethod
    def _local_day_bounds(now: Optional[datetime] = None) -> Tuple[str, str]:
        """Return (start, end) ISO bounds of the local calendar day in stored UTC space."""
        now = now or datetime.now()
        local_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        offset = now.astimezone().utcoffset() or timedelta(0)
        start = local_midnight - offset
        return start.isoformat(), (start + timedelta(days=1)).isoformat()

    def has_attendance_today(
        self,
        user_id: str,
        direction: str = "in",
        now: Optional[datetime] = None,
    ) -> bool:
        """
        True if the user already has a record of ``direction`` for the local day.

        Used to guarantee at most one *masuk* (in) and one *pulang* (out) record
        per user per day, regardless of how many times the face is recognised.
        """
        direction = "out" if str(direction).lower() in ("out", "pulang") else "in"
        start, end = self._local_day_bounds(now)
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT 1 FROM attendance
                   WHERE user_id = ? AND direction = ? AND timestamp >= ? AND timestamp < ?
                   LIMIT 1""",
                (user_id, direction, start, end),
            ).fetchone()
        return row is not None

    def get_today_last_direction(
        self,
        user_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Direction of the user's most recent record on the local day, or None.

        Attendance alternates masuk -> pulang -> masuk -> pulang..., so the last
        record decides what may be logged next: after a *pulang* the user may
        check in again, while an open *masuk* blocks a second *masuk* and an
        absent *masuk* blocks *pulang*.
        """
        start, end = self._local_day_bounds(now)
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT direction FROM attendance
                   WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (user_id, start, end),
            ).fetchone()
        return (row["direction"] or "in") if row else None

    def get_today_record(
        self,
        user_id: str,
        direction: str = "in",
        now: Optional[datetime] = None,
    ) -> Optional[str]:
        """Return the timestamp of today's record for ``direction``, if any."""
        direction = "out" if str(direction).lower() in ("out", "pulang") else "in"
        start, end = self._local_day_bounds(now)
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT timestamp FROM attendance
                   WHERE user_id = ? AND direction = ? AND timestamp >= ? AND timestamp < ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (user_id, direction, start, end),
            ).fetchone()
        return row["timestamp"] if row else None

    def get_today_status(self, now: Optional[datetime] = None) -> Dict[str, Dict[str, bool]]:
        """Per-user check-in/out status for the local day (user_id -> {in, out})."""
        start, end = self._local_day_bounds(now)
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT DISTINCT user_id, direction FROM attendance
                   WHERE timestamp >= ? AND timestamp < ?""",
                (start, end),
            ).fetchall()
        status: Dict[str, Dict[str, bool]] = {}
        for r in rows:
            entry = status.setdefault(r["user_id"], {"in": False, "out": False})
            if r["direction"] == "out":
                entry["out"] = True
            else:
                entry["in"] = True
        return status

    def get_unsynced_records(self, limit: int = 50) -> List[AttendanceRecord]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM attendance WHERE synced = 0 ORDER BY timestamp LIMIT ?""",
                (limit,),
            ).fetchall()
            return [
                AttendanceRecord(
                    id=r["id"],
                    user_id=r["user_id"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    similarity=r["similarity"],
                    liveness_score=r["liveness_score"],
                    synced=bool(r["synced"]),
                    device_id=r["device_id"],
                    direction=r["direction"] or "in",
                )
                for r in rows
            ]

    def list_attendance(self, limit: int = 50) -> List[AttendanceRecord]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT a.*, u.name AS user_name FROM attendance a
                   LEFT JOIN users u ON u.id = a.user_id
                   ORDER BY a.timestamp DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [
                AttendanceRecord(
                    id=r["id"],
                    user_id=r["user_id"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    similarity=r["similarity"],
                    liveness_score=r["liveness_score"],
                    synced=bool(r["synced"]),
                    device_id=r["device_id"],
                    direction=r["direction"] or "in",
                    name=r["user_name"],
                )
                for r in rows
            ]

    def get_attendance_summary(self) -> Dict[str, Dict[str, Any]]:
        """Per-user attendance counts and last timestamp (user_id -> {count, last})."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT user_id, COUNT(*) AS cnt, MAX(timestamp) AS last
                   FROM attendance GROUP BY user_id"""
            ).fetchall()
        return {
            r["user_id"]: {"count": int(r["cnt"]), "last": r["last"]}
            for r in rows
        }

    def clear_attendance(self) -> int:
        """Delete all attendance records. Returns the number removed."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM attendance")
            conn.commit()
            return cur.rowcount

    def mark_synced(self, record_ids: List[str]) -> int:
        if not record_ids:
            return 0
        placeholders = ",".join("?" * len(record_ids))
        with self._get_conn() as conn:
            cur = conn.execute(
                f"UPDATE attendance SET synced = 1 WHERE id IN ({placeholders})",
                record_ids,
            )
            conn.commit()
            return cur.rowcount

    def get_attendance_stats(self, user_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        with self._get_conn() as conn:
            if user_id:
                rows = conn.execute(
                    """SELECT * FROM attendance
                       WHERE user_id = ? AND timestamp >= datetime('now', ?)
                       ORDER BY timestamp""",
                    (user_id, f"-{days} days"),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM attendance
                       WHERE timestamp >= datetime('now', ?)
                       ORDER BY timestamp""",
                    (f"-{days} days",),
                ).fetchall()

            return {
                "total": len(rows),
                "users": len(set(r["user_id"] for r in rows)),
                "synced": sum(1 for r in rows if r["synced"]),
                "pending": sum(1 for r in rows if not r["synced"]),
            }
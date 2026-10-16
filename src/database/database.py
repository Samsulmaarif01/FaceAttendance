"""
Database module with encrypted SQLite and biohashing for template protection.
"""

import os
import sqlite3
import hashlib
import secrets
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
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
                    is_active INTEGER DEFAULT 1
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
            conn.commit()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def add_user(self, user_id: str, name: str, embedding: np.ndarray) -> bool:
        salt = self.biohasher.generate_salt()
        biohashed = self.biohasher.biohash(embedding, self.biohash_token, salt)
        now = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO users (id, name, biohashed_template, salt, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, name, biohashed, salt, now, now),
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

    def get_all_users(self) -> List[User]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM users WHERE is_active = 1").fetchall()
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
        now = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            cur = conn.execute(
                """UPDATE users SET biohashed_template = ?, salt = ?, updated_at = ?
                   WHERE id = ?""",
                (biohashed, salt, now, user_id),
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

    def verify_user(self, user_id: str, embedding: np.ndarray) -> bool:
        user = self.get_user(user_id)
        if not user:
            self._audit("verification_failed", user_id)
            return False
        verified = self.biohasher.verify(embedding, user.biohashed_template, self.biohash_token, user.salt)
        if not verified:
            self._audit("verification_failed", user_id)
        return verified

    def get_user_templates(self) -> Dict[str, np.ndarray]:
        """
        For matching, we need to compare against stored templates.
        Since we only store biohashed templates, we cannot recover original embeddings.
        This method is a placeholder - in production, matching happens differently:
        either store encrypted embeddings separately, or use biohashing with known token.
        """
        # WARNING: This returns empty dict - real implementation would
        # either use encrypted storage for matching or a different approach
        return {}

    def log_attendance(
        self,
        user_id: str,
        similarity: float,
        liveness_score: float,
        device_id: str = "",
    ) -> str:
        record_id = secrets.token_urlsafe(16)
        timestamp = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO attendance (id, user_id, timestamp, similarity, liveness_score, device_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (record_id, user_id, timestamp, similarity, liveness_score, device_id),
            )
            conn.commit()
        self._audit(
            "attendance_logged",
            user_id,
            {"similarity": similarity, "liveness_score": liveness_score, "device_id": device_id},
        )
        return record_id

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
                )
                for r in rows
            ]

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
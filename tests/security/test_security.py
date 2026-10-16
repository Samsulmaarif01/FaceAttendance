"""Tests for the security hardening module (phase 3)."""

import numpy as np
import pytest
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.x509.oid import NameOID

from src.security import (
    AuditLog,
    FileKeyStore,
    HardwareKeyStore,
    KeyStore,
    create_client_context,
    create_server_context,
    generate_self_signed_cert,
    generate_signed_cert,
)
from src.database.database import BioHasher, Database


class TestKeyStore:
    def test_file_backend_persists_key(self, tmp_path):
        path = str(tmp_path / "db.key")
        store = KeyStore(FileKeyStore(path))
        key = store.get_or_create_key()
        assert key is not None
        assert store.get_or_create_key() == key

    def test_rotate_key_changes_key(self, tmp_path):
        store = KeyStore(FileKeyStore(str(tmp_path / "db.key")))
        first = store.get_or_create_key()
        rotated = store.rotate_key()
        assert rotated != first
        assert store.get_or_create_key() == rotated

    def test_hardware_backend_unavailable(self):
        backend = HardwareKeyStore()
        assert backend.is_available() is False
        with pytest.raises(NotImplementedError):
            backend.load()
        with pytest.raises(NotImplementedError):
            backend.store(b"key")


class TestAuditLog:
    def test_log_and_verify_chain(self, tmp_path):
        log = AuditLog(str(tmp_path / "audit.log"))
        log.log("enrollment", user_id="u1", details={"name": "Alice"})
        log.log("recognition", user_id="u1", details={"similarity": 0.91})

        assert log.count() == 2
        events = log.get_events()
        assert events[0].event_type == "enrollment"
        assert events[1].prev_hash == events[0].hash
        assert log.verify_chain() is True

    def test_tamper_is_detected(self, tmp_path):
        path = tmp_path / "audit.log"
        log = AuditLog(str(path))
        log.log("enrollment", user_id="u1")
        log.log("recognition", user_id="u1")

        lines = path.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace('"u1"', '"u2"')
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        assert log.verify_chain() is False

    def test_deletion_of_middle_entry_is_detected(self, tmp_path):
        path = tmp_path / "audit.log"
        log = AuditLog(str(path))
        log.log("a")
        log.log("b")
        log.log("c")

        lines = path.read_text(encoding="utf-8").splitlines()
        del lines[1]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        assert log.verify_chain() is False


class TestBioHashCancelability:
    def test_verify_and_token_dependence(self):
        hasher = BioHasher()
        embedding = np.random.randn(512).astype(np.float32)
        token = b"device-token-a"
        salt = hasher.generate_salt()

        template = hasher.biohash(embedding, token, salt)
        assert hasher.verify(embedding, template, token, salt) is True
        assert hasher.verify(embedding, template, b"other-token", salt) is False

        other_embedding = np.random.randn(512).astype(np.float32)
        assert hasher.verify(other_embedding, template, token, salt) is False

    def test_same_embedding_same_token_is_deterministic(self):
        hasher = BioHasher()
        embedding = np.ones(512, dtype=np.float32)
        salt = b"fixed-salt-000000"
        assert hasher.biohash(embedding, b"t", salt) == hasher.biohash(embedding, b"t", salt)


class TestTLS:
    def _common_name(self, cert_path):
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        return cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value

    def test_self_signed_cert_generation(self, tmp_path):
        cert = str(tmp_path / "server.pem")
        key = str(tmp_path / "server.key")
        generate_self_signed_cert(cert, key, common_name="node-1")

        assert self._common_name(cert) == "node-1"
        assert create_server_context(cert, key) is not None

    def test_ca_signed_cert_and_mtls_contexts(self, tmp_path):
        ca_cert = str(tmp_path / "ca.pem")
        ca_key = str(tmp_path / "ca.key")
        generate_self_signed_cert(ca_cert, ca_key, common_name="face-ca", is_ca=True)

        node_cert = str(tmp_path / "node.pem")
        node_key = str(tmp_path / "node.key")
        generate_signed_cert(node_cert, node_key, ca_cert, ca_key, common_name="node-1")

        with open(node_cert, "rb") as f:
            parsed = x509.load_pem_x509_certificate(f.read())
        with open(ca_cert, "rb") as f:
            ca_parsed = x509.load_pem_x509_certificate(f.read())
        assert parsed.issuer == ca_parsed.subject

        assert create_server_context(node_cert, node_key, ca_path=ca_cert) is not None
        assert create_client_context(node_cert, node_key, ca_path=ca_cert) is not None


class TestAuditIntegration:
    def _make_db(self, tmp_path, audit_log):
        return Database(
            db_path=str(tmp_path / "attendance.db"),
            encryption_key=Fernet.generate_key(),
            biohash_token=b"test-token",
            audit_log=audit_log,
        )

    def test_database_writes_audit_events(self, tmp_path):
        log = AuditLog(str(tmp_path / "audit.log"))
        db = self._make_db(tmp_path, log)
        embedding = np.random.randn(512).astype(np.float32)

        db.add_user("u1", "Alice", embedding)
        db.verify_user("u1", embedding)
        db.verify_user("missing", embedding)
        db.update_user_embedding("u1", embedding)
        db.log_attendance("u1", similarity=0.95, liveness_score=0.9)
        db.delete_user("u1")

        event_types = [event.event_type for event in log.get_events()]
        assert "user_enrolled" in event_types
        assert "verification_failed" in event_types
        assert "template_updated" in event_types
        assert "attendance_logged" in event_types
        assert "user_deleted" in event_types
        assert log.verify_chain() is True

    def test_database_without_audit_log(self, tmp_path):
        db = self._make_db(tmp_path, None)
        assert db.audit_log is None
        embedding = np.ones(512, dtype=np.float32)
        assert db.add_user("u1", "Alice", embedding) is True
        assert db.log_attendance("u1", 0.9, 0.8) != ""

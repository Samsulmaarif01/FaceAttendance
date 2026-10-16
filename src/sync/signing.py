"""
Ed25519 payload signing for sync uploads.

Each node signs the compressed payload with its own private key so the server
(and peer nodes) can verify authenticity and detect tampering or replay. Keys
are exchanged as PEM bytes; signing lives here so it can be tested without any
network transport.
"""

import base64
import binascii
import json
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def generate_keypair() -> Tuple[bytes, bytes]:
    """Return ``(private_pem, public_pem)`` for a fresh Ed25519 keypair."""
    private_key = Ed25519PrivateKey.generate()
    return (
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )


def _load_private(private_pem: bytes) -> Ed25519PrivateKey:
    return serialization.load_pem_private_key(private_pem, password=None)


def _load_public(public_pem: bytes) -> Ed25519PublicKey:
    return serialization.load_pem_public_key(public_pem)


def sign_payload(private_pem: bytes, payload: bytes) -> bytes:
    return _load_private(private_pem).sign(payload)


def verify_payload(public_pem: bytes, payload: bytes, signature: bytes) -> bool:
    try:
        _load_public(public_pem).verify(signature, payload)
        return True
    except InvalidSignature:
        return False


def sign_envelope(private_pem: bytes, payload: bytes) -> bytes:
    """Wrap ``payload`` with a detached signature as a JSON envelope."""
    signature = sign_payload(private_pem, payload)
    envelope: Dict[str, Any] = {
        "payload": base64.b64encode(payload).decode("ascii"),
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def open_envelope(public_pem: bytes, envelope: bytes) -> Optional[bytes]:
    """Return the payload if the signature verifies, else ``None``.

    Malformed or tampered envelopes fail safe by returning ``None`` rather
    than raising, so callers can treat any failure as "reject".
    """
    try:
        data = json.loads(envelope.decode("utf-8"))
        payload = base64.b64decode(data["payload"])
        signature = base64.b64decode(data["signature"])
    except (json.JSONDecodeError, KeyError, ValueError, UnicodeDecodeError, binascii.Error):
        return None
    return payload if verify_payload(public_pem, payload, signature) else None

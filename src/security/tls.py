"""
Self-signed certificate generation and mTLS SSL context helpers for sync.

Certificates are generated locally (offline-first) so nodes can authenticate
each other without a public CA.
"""

import datetime
import ipaddress
import os
import ssl
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

_ONE_DAY = datetime.timedelta(days=1)


def _ensure_parent(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def _write_key(key, key_path: str) -> None:
    _ensure_parent(key_path)
    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )


def _write_cert(cert, cert_path: str) -> None:
    _ensure_parent(cert_path)
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def _subject(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _add_san(builder: x509.CertificateBuilder, common_name: str) -> x509.CertificateBuilder:
    return builder.add_extension(
        x509.SubjectAlternativeName(
            [
                x509.DNSName(common_name),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            ]
        ),
        critical=False,
    )


def generate_self_signed_cert(
    cert_path: str,
    key_path: str,
    common_name: str = "face-attendance",
    days: int = 365,
    is_ca: bool = False,
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = _subject(common_name)
    now = datetime.datetime.utcnow()

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + _ONE_DAY * days)
        .add_extension(
            x509.BasicConstraints(ca=is_ca, path_length=None), critical=True
        )
    )
    if not is_ca:
        builder = _add_san(builder, common_name)

    cert = builder.sign(key, hashes.SHA256())
    _write_key(key, key_path)
    _write_cert(cert, cert_path)


def generate_signed_cert(
    cert_path: str,
    key_path: str,
    ca_cert_path: str,
    ca_key_path: str,
    common_name: str = "face-attendance-node",
    days: int = 365,
) -> None:
    with open(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    with open(ca_key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), password=None)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.datetime.utcnow()

    builder = (
        x509.CertificateBuilder()
        .subject_name(_subject(common_name))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + _ONE_DAY * days)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .add_extension(
            x509.ExtendedKeyUsage(
                [x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                 x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]
            ),
            critical=False,
        )
    )
    builder = _add_san(builder, common_name)

    cert = builder.sign(ca_key, hashes.SHA256())
    _write_key(key, key_path)
    _write_cert(cert, cert_path)


def create_server_context(
    cert_path: str,
    key_path: str,
    ca_path: Optional[str] = None,
) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    if ca_path:
        context.load_verify_locations(ca_path)
        context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return context


def create_client_context(
    cert_path: str,
    key_path: str,
    ca_path: str,
) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_path)
    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return context

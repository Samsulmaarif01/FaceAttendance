"""
Device key storage abstraction for template protection and encryption.

Provides a file-backed backend usable today and a hardware (TPM / secure
element) backend interface for platforms that expose one.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional

from cryptography.fernet import Fernet


class KeyStoreBackend(ABC):
    @abstractmethod
    def load(self) -> Optional[bytes]:
        pass

    @abstractmethod
    def store(self, key: bytes) -> None:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class FileKeyStore(KeyStoreBackend):
    """Stores the key as a file on disk with owner-only permissions."""

    def __init__(self, path: str = "data/db.key"):
        self.path = path

    def load(self) -> Optional[bytes]:
        if not os.path.exists(self.path):
            return None
        with open(self.path, "rb") as f:
            return f.read()

    def store(self, key: bytes) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "wb") as f:
            f.write(key)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def is_available(self) -> bool:
        return True


class HardwareKeyStore(KeyStoreBackend):
    """TPM / secure element backend. Not available on this platform yet."""

    def load(self) -> Optional[bytes]:
        raise NotImplementedError("No TPM/secure element backend available")

    def store(self, key: bytes) -> None:
        raise NotImplementedError("No TPM/secure element backend available")

    def is_available(self) -> bool:
        return False


class KeyStore:
    def __init__(
        self,
        backend: Optional[KeyStoreBackend] = None,
        path: str = "data/db.key",
    ):
        self.backend = backend if backend is not None else FileKeyStore(path)

    def get_or_create_key(self) -> bytes:
        key = self.backend.load()
        if key is None:
            key = Fernet.generate_key()
            self.backend.store(key)
        return key

    def rotate_key(self) -> bytes:
        key = Fernet.generate_key()
        self.backend.store(key)
        return key

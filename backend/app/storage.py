"""StorageService: a small interface over blob storage, backed today by the
local filesystem under STORAGE_PATH (see PROJECT_SPEC.md — S3 later, behind
the same interface).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings


class StorageService(ABC):
    @abstractmethod
    def save_bytes(self, key: str, data: bytes) -> str:
        """Persist `data` under `key`; returns the storage key."""

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        """Read back the bytes stored under `key`."""

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalStorageService(StorageService):
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root if root is not None else get_settings().STORAGE_PATH).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError(f"storage key escapes storage root: {key!r}")
        return path

    def save_bytes(self, key: str, data: bytes) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read_bytes(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()


def get_storage_service() -> StorageService:
    """FastAPI dependency: local storage today, swap for an S3 impl later."""
    return LocalStorageService()

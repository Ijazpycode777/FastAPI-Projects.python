"""Persistent file storage for study materials.

Local backend writes to a configured directory (Render Disk mounts here).
S3 backend is stubbed for production; configure credentials to enable.
File bytes are never stored in PostgreSQL.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import AppException


class StorageBackend:
    def save(self, key: str, stream: BinaryIO, content_type: str) -> str: ...  # pragma: no cover
    def open(self, key: str) -> BinaryIO: ...  # pragma: no cover
    def delete(self, key: str) -> None: ...  # pragma: no cover
    def exists(self, key: str) -> bool: ...  # pragma: no cover


class LocalStorage(StorageBackend):
    def __init__(self, base_path: str = settings.storage_local_path) -> None:
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal: only the basename is used.
        safe = Path(key).name
        return self.base / safe

    def save(self, key: str, stream: BinaryIO, content_type: str) -> str:
        path = self._path(key)
        with path.open("wb") as fh:
            shutil.copyfileobj(stream, fh)
        return str(path)

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.exists():
            raise AppException("File not found.", status_code=404, code="NOT_FOUND")
        return path.open("rb")

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3Storage(StorageBackend):  # pragma: no cover - requires credentials
    def __init__(self) -> None:
        try:
            import boto3  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("boto3 not installed; cannot use S3 backend.") from exc
        self._bucket = settings.storage_s3_bucket
        self._client = None  # configured lazily in production

    def save(self, key: str, stream: BinaryIO, content_type: str) -> str:
        raise NotImplementedError("S3 backend must be configured with credentials in production.")

    def open(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


def get_storage() -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage()


def make_storage_key(filename: str, prefix: str = "materials") -> str:
    """Generate a unique, safe storage key."""
    import uuid
    ext = os.path.splitext(filename)[1]
    return f"{prefix}/{uuid.uuid4().hex}{ext}"

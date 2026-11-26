"""Knovera storage module."""

from functools import lru_cache
from backend.app.core.config import get_settings
from backend.app.storage.base import StorageService
from backend.app.storage.local import LocalStorageService
from backend.app.storage.exceptions import (
    StorageError,
    FileTooLargeError,
    PathTraversalError,
    StorageFileNotFoundError,
)

__all__ = [
    "StorageService",
    "LocalStorageService",
    "StorageError",
    "FileTooLargeError",
    "PathTraversalError",
    "StorageFileNotFoundError",
    "get_storage_service",
]


@lru_cache
def get_storage_service() -> StorageService:
    """Returns singleton StorageService configured via application settings."""
    settings = get_settings()
    return LocalStorageService(settings.resolved_storage_root)

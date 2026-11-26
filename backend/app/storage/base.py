"""Abstract base class for Knovera file storage services."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Tuple
from fastapi import UploadFile


class StorageService(ABC):
    """Defines private file storage operations for documents."""

    @abstractmethod
    async def save_upload(
        self,
        upload_file: UploadFile,
        storage_key: str,
        max_size_bytes: int,
    ) -> Tuple[int, str]:
        """Streams an uploaded file to storage_key while calculating SHA-256 and enforcing max size.

        Returns:
            Tuple of (file_size_bytes, sha256_hexdigest).
        """
        pass

    @abstractmethod
    def open_file(self, storage_key: str) -> BinaryIO:
        """Opens the stored file for reading in binary mode."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Deletes the stored file at storage_key. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Checks if a file exists at storage_key."""
        pass

    @abstractmethod
    def get_absolute_path(self, storage_key: str) -> Path:
        """Resolves the safe absolute path for storage_key, strictly preventing traversal."""
        pass

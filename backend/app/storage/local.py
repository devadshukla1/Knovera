"""Local filesystem storage service for private document storage."""

import hashlib
import os
from pathlib import Path
from typing import BinaryIO, Tuple
import uuid
from fastapi import UploadFile

from backend.app.core.logging import get_logger
from backend.app.storage.base import StorageService
from backend.app.storage.exceptions import (
    FileTooLargeError,
    PathTraversalError,
    StorageError,
    StorageFileNotFoundError,
)

logger = get_logger("knovera.storage")


class LocalStorageService(StorageService):
    """Stores files on the local filesystem within a configured private root directory."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorageService initialized with root: %s", self.root_dir)

    def get_absolute_path(self, storage_key: str) -> Path:
        """Resolves storage_key against root_dir and verifies it does not escape root_dir."""
        raw_path = Path(storage_key)
        if raw_path.is_absolute():
            logger.warning("Security violation: absolute storage key rejected: %s", storage_key)
            raise PathTraversalError(f"Absolute storage key not allowed: {storage_key}")

        candidate = (self.root_dir / raw_path).resolve()

        # Strict containment check
        try:
            candidate.relative_to(self.root_dir)
        except ValueError:
            logger.warning(
                "Security violation: path traversal attempt detected for key: %s",
                storage_key,
            )
            raise PathTraversalError(f"Invalid storage key: {storage_key}")

        return candidate

    async def save_upload(
        self,
        upload_file: UploadFile,
        storage_key: str,
        max_size_bytes: int,
    ) -> Tuple[int, str]:
        """Saves an UploadFile stream atomically while computing SHA-256 and enforcing max size.

        Returns:
            Tuple of (total_bytes, sha256_hex)
        """
        target_path = self.get_absolute_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        temp_filename = f".tmp_{uuid.uuid4().hex}_{target_path.name}"
        temp_path = target_path.parent / temp_filename

        hasher = hashlib.sha256()
        total_bytes = 0
        chunk_size = 64 * 1024  # 64KB bounded chunks

        try:
            with open(temp_path, "wb") as f:
                while True:
                    chunk = await upload_file.read(chunk_size)
                    if not chunk:
                        break

                    total_bytes += len(chunk)
                    if total_bytes > max_size_bytes:
                        raise FileTooLargeError(
                            f"Uploaded file exceeds maximum limit of {max_size_bytes} bytes."
                        )

                    hasher.update(chunk)
                    f.write(chunk)

            # Atomic replace to prevent partial writes
            os.replace(temp_path, target_path)
            logger.info(
                "Stored file %s (%d bytes, sha256=%s)",
                target_path.name,
                total_bytes,
                hasher.hexdigest(),
            )
            return total_bytes, hasher.hexdigest()

        except Exception as exc:
            # Clean up temp file on any error
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError as cleanup_err:
                    logger.warning("Failed to clean up temp file %s: %s", temp_path, cleanup_err)
            if isinstance(exc, (FileTooLargeError, PathTraversalError)):
                raise
            logger.exception("Storage write failed for %s", storage_key)
            raise StorageError(f"Failed to store uploaded file: {exc}") from exc

    def open_file(self, storage_key: str) -> BinaryIO:
        """Opens the stored file for reading."""
        path = self.get_absolute_path(storage_key)
        if not path.is_file():
            raise StorageFileNotFoundError(f"File not found at storage key: {storage_key}")
        return open(path, "rb")

    def delete_file(self, storage_key: str) -> bool:
        """Deletes the stored file."""
        try:
            path = self.get_absolute_path(storage_key)
            if not path.is_file():
                return False
            path.unlink()
            # Clean empty parent directories up to root
            parent = path.parent
            while parent != self.root_dir:
                try:
                    parent.rmdir()
                    parent = parent.parent
                except OSError:
                    break
            logger.info("Deleted file at storage key: %s", storage_key)
            return True
        except PathTraversalError:
            raise
        except Exception as exc:
            logger.exception("Error deleting file at key %s", storage_key)
            raise StorageError(f"Failed to delete file: {exc}") from exc

    def exists(self, storage_key: str) -> bool:
        """Checks if a file exists at storage_key."""
        try:
            path = self.get_absolute_path(storage_key)
            return path.is_file()
        except PathTraversalError:
            return False

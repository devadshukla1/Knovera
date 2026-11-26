"""Unit tests for Knovera LocalStorageService."""

import io
from pathlib import Path
import pytest
from fastapi import UploadFile

from backend.app.storage.exceptions import (
    FileTooLargeError,
    PathTraversalError,
    StorageFileNotFoundError,
)
from backend.app.storage.local import LocalStorageService


@pytest.fixture
def temp_storage(tmp_path: Path) -> LocalStorageService:
    storage_root = tmp_path / "documents"
    return LocalStorageService(storage_root)


@pytest.mark.asyncio
async def test_save_and_read_upload(temp_storage: LocalStorageService):
    content = b"%PDF-1.4\nTest PDF file content\n%%EOF"
    upload_file = UploadFile(
        file=io.BytesIO(content),
        filename="test.pdf",
    )

    storage_key = "workspaces/ws-1/doc-1/original.pdf"
    file_size, sha256_hex = await temp_storage.save_upload(
        upload_file=upload_file,
        storage_key=storage_key,
        max_size_bytes=1024,
    )

    assert file_size == len(content)
    assert len(sha256_hex) == 64
    assert temp_storage.exists(storage_key)

    with temp_storage.open_file(storage_key) as f:
        read_content = f.read()
    assert read_content == content


@pytest.mark.asyncio
async def test_path_traversal_prevention(temp_storage: LocalStorageService):
    upload_file = UploadFile(
        file=io.BytesIO(b"malicious"),
        filename="evil.pdf",
    )

    with pytest.raises(PathTraversalError):
        await temp_storage.save_upload(
            upload_file=upload_file,
            storage_key="../outside.pdf",
            max_size_bytes=1024,
        )

    with pytest.raises(PathTraversalError):
        temp_storage.get_absolute_path("/etc/passwd")

    with pytest.raises(PathTraversalError):
        temp_storage.get_absolute_path("workspaces/../../secret.txt")


@pytest.mark.asyncio
async def test_file_too_large_rejection_and_cleanup(temp_storage: LocalStorageService):
    large_content = b"A" * 2000
    upload_file = UploadFile(
        file=io.BytesIO(large_content),
        filename="large.pdf",
    )

    storage_key = "workspaces/ws-1/doc-large/original.pdf"
    max_size = 500

    with pytest.raises(FileTooLargeError):
        await temp_storage.save_upload(
            upload_file=upload_file,
            storage_key=storage_key,
            max_size_bytes=max_size,
        )

    # Verify no file remains
    assert not temp_storage.exists(storage_key)


def test_delete_and_not_found(temp_storage: LocalStorageService):
    with pytest.raises(StorageFileNotFoundError):
        temp_storage.open_file("non-existent-key")

    assert not temp_storage.delete_file("non-existent-key")

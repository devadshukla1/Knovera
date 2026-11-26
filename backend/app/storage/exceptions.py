"""Storage service exceptions."""


class StorageError(Exception):
    """Base exception for storage errors."""
    pass


class FileTooLargeError(StorageError):
    """Raised when an uploaded file exceeds the configured size limit."""
    pass


class PathTraversalError(StorageError):
    """Raised when a storage key resolves outside the allowed root directory."""
    pass


class StorageFileNotFoundError(StorageError):
    """Raised when a requested stored file does not exist."""
    pass

"""Knovera Pydantic schemas registry."""

from backend.app.schemas.document import (
    DocumentResponse,
    DocumentDetailResponse,
    DocumentPageResponse,
    DocumentPagesListResponse,
)
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
)
from backend.app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
)

__all__ = [
    "DocumentResponse",
    "DocumentDetailResponse",
    "DocumentPageResponse",
    "DocumentPagesListResponse",
    "WorkspaceCreate",
    "WorkspaceUpdate",
    "WorkspaceResponse",
    "UserRegister",
    "UserLogin",
    "TokenResponse",
    "UserResponse",
]

"""FastAPI dependencies for local single-user execution and workspace management."""

from typing import Optional
import uuid
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.auth import decode_access_token
from backend.app.core.local_user import get_or_create_local_user
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.workspace import Workspace

logger = get_logger("knovera.api.deps")

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolves the current user.

    In local single-user mode, authentication is non-mandatory:
    - If a valid Bearer token is provided and corresponds to an active user, returns that user.
    - Otherwise (missing, expired, or invalid token), automatically resolves to the
      persistent local application owner user.
    Never rejects local requests with HTTP 401.
    """
    token: Optional[str] = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if token:
        try:
            user_id = decode_access_token(token)
            user = db.query(User).filter(User.id == user_id, User.status == "active").first()
            if user:
                return user
        except Exception:
            # Fall through to local owner in local mode
            pass

    return get_or_create_local_user(db)


def get_user_workspace(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    """Verifies that the workspace exists in the local database.

    In local single-user mode, workspace permission checks are removed:
    all workspaces are accessible to the local user.
    """
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id)
        .first()
    )

    if not workspace:
        logger.warning(
            "Workspace not found: workspace_id=%s",
            workspace_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # When an explicit non-local user token is provided in multi-user test suites, enforce isolation
    from backend.app.core.local_user import LOCAL_USER_ID
    if current_user.id != LOCAL_USER_ID and workspace.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    return workspace

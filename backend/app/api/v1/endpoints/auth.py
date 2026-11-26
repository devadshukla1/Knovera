"""Authentication API endpoints for Knovera."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.auth import create_access_token, hash_password, verify_password
from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Creates a new user and issues a signed JWT access token."""
    normalized_email = payload.email.lower().strip()
    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    now_utc = datetime.now(timezone.utc)
    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        status="active",
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    settings = get_settings()
    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in_minutes=settings.AUTH_ACCESS_TOKEN_MINUTES,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and return JWT access token",
)
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Verifies user credentials and returns a signed access token."""
    normalized_email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled or inactive",
        )

    settings = get_settings()
    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in_minutes=settings.AUTH_ACCESS_TOKEN_MINUTES,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Returns profile for currently authenticated user."""
    return current_user

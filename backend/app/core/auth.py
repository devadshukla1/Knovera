"""Authentication utilities: Argon2id password hashing and signed JWT tokens."""

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger

logger = get_logger("knovera.auth")
hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash."""
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(
    user_id: uuid.UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates a signed short-lived JWT access token."""
    settings = get_settings()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.AUTH_ACCESS_TOKEN_MINUTES)

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    secret = settings.AUTH_SECRET_KEY.get_secret_value()
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str) -> uuid.UUID:
    """Decodes and validates a JWT access token, returning the user_id UUID."""
    settings = get_settings()
    secret = settings.AUTH_SECRET_KEY.get_secret_value()
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        sub = payload.get("sub")
        if not sub:
            raise ValueError("Token missing 'sub' subject claim.")
        return uuid.UUID(sub)
    except (jwt.PyJWTError, ValueError) as exc:
        logger.debug("Access token decoding failed: %s", exc)
        raise ValueError(f"Invalid or expired token: {exc}") from exc

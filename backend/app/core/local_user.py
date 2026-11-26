"""Local application owner identity management for local-first single-user execution."""

from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.user import User

logger = get_logger("knovera.core.local_user")

LOCAL_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
LOCAL_USER_EMAIL = "local@knovera.internal"
LOCAL_USER_DISPLAY_NAME = "Local Owner"


def get_or_create_local_user(db: Session) -> User:
    """Retrieves or automatically provisions the persistent local owner user.

    In local single-user mode, this user record serves as the default owner for
    workspaces, documents, quizzes, and learner analytics, ensuring all foreign
    key constraints in PostgreSQL are strictly satisfied without requiring login,
    registration, or JWT credentials.
    """
    # 1. Lookup by deterministic local UUID
    user = db.query(User).filter(User.id == LOCAL_USER_ID).first()
    if user:
        if user.status != "active":
            user.status = "active"
            db.commit()
            db.refresh(user)
        return user

    # 2. Lookup by fixed local email
    user = db.query(User).filter(User.email == LOCAL_USER_EMAIL).first()
    if user:
        if user.status != "active":
            user.status = "active"
            db.commit()
            db.refresh(user)
        return user

    # 3. If any active user exists from prior sessions or migrations, reuse it
    existing_user = (
        db.query(User)
        .filter(User.status == "active")
        .order_by(User.created_at.asc())
        .first()
    )
    if existing_user:
        return existing_user

    # 4. Provision persistent local owner identity
    now_utc = datetime.now(timezone.utc)
    user = User(
        id=LOCAL_USER_ID,
        email=LOCAL_USER_EMAIL,
        password_hash="local_disabled",
        display_name=LOCAL_USER_DISPLAY_NAME,
        status="active",
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Provisioned persistent local owner user: id=%s, email=%s", user.id, user.email)
    return user

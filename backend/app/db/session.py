"""SQLAlchemy session management and PostgreSQL connectivity checks.

Configures connection pooling with lazy connection checkout and pre-ping,
ensuring the application boots reliably even when the database is unavailable.
"""

import time
from typing import Generator, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger

logger = get_logger("knovera.db")
settings = get_settings()

# Configure engine kwargs
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_size": settings.DB_POOL_SIZE,
    "max_overflow": settings.DB_MAX_OVERFLOW,
    "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
    "pool_timeout": settings.DB_POOL_TIMEOUT_SECONDS,
}

# Add driver-specific connection timeout or SQLite multi-threading flags
if settings.sqlalchemy_database_uri.startswith("postgresql"):
    engine_kwargs["connect_args"] = {"connect_timeout": 2}
elif settings.sqlalchemy_database_uri.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.sqlalchemy_database_uri, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency generator that yields an isolated database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connectivity() -> Tuple[bool, Optional[float], Optional[str]]:
    """Executes a lightweight query (SELECT 1) to verify database connectivity.

    Returns:
        Tuple of (is_connected, latency_ms, error_message).
        When connected: (True, latency_ms, None)
        When disconnected: (False, None, "Database service unavailable")
    """
    start_time = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        return True, round(latency_ms, 2), None
    except Exception as exc:
        logger.warning("Database connectivity check failed: %s", type(exc).__name__)
        return False, None, "Database service unavailable"

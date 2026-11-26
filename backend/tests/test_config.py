"""Tests for Pydantic Settings and URI generation in Knovera."""

from pydantic import SecretStr
from backend.app.core.config import Settings, get_settings


def test_default_settings_values() -> None:
    """Settings defaults adhere to Phase 0 specification."""
    s = get_settings()
    assert s.APP_ENV in ("development", "test", "production")
    assert s.APP_PORT == 8000
    assert s.POSTGRES_PORT == 5432
    assert s.POSTGRES_DB == "knovera"
    assert s.POSTGRES_USER == "knovera_app"
    assert s.CHROMA_PORT == 8001
    assert s.FRONTEND_ORIGIN == "http://localhost:5173"


def test_sqlalchemy_database_uri_assembly() -> None:
    """Computed sqlalchemy_database_uri builds valid psycopg scheme."""
    s = Settings(
        POSTGRES_HOST="db.local",
        POSTGRES_PORT=5433,
        POSTGRES_DB="testdb",
        POSTGRES_USER="testuser",
        POSTGRES_PASSWORD=SecretStr("secretpass123"),
        DATABASE_URL=None,
    )
    uri = s.sqlalchemy_database_uri
    assert uri == "postgresql+psycopg://testuser:secretpass123@db.local:5433/testdb"


def test_custom_database_url_normalization() -> None:
    """Custom DATABASE_URL normalizes postgres:// to postgresql+psycopg://."""
    s1 = Settings(DATABASE_URL="postgres://user:pass@host:5432/db")
    assert s1.sqlalchemy_database_uri == "postgresql+psycopg://user:pass@host:5432/db"

    s2 = Settings(DATABASE_URL="postgresql://user:pass@host:5432/db")
    assert s2.sqlalchemy_database_uri == "postgresql+psycopg://user:pass@host:5432/db"

    s3 = Settings(DATABASE_URL="postgresql+psycopg://user:pass@host:5432/db")
    assert s3.sqlalchemy_database_uri == "postgresql+psycopg://user:pass@host:5432/db"


def test_safe_database_uri_masks_credentials() -> None:
    """safe_database_uri always masks passwords."""
    s = Settings(
        POSTGRES_HOST="db.local",
        POSTGRES_PORT=5432,
        POSTGRES_DB="testdb",
        POSTGRES_USER="myuser",
        POSTGRES_PASSWORD=SecretStr("supersecretpassword"),
        DATABASE_URL=None,
    )
    safe = s.safe_database_uri
    assert "supersecretpassword" not in safe
    assert "myuser" in safe
    assert "***" in safe
    assert "db.local" in safe


def test_secret_fields_masked_in_repr() -> None:
    """Sensitive SecretStr fields and database URLs are masked in repr(settings)."""
    s = Settings(
        POSTGRES_USER="app_user",
        POSTGRES_PASSWORD=SecretStr("sensitive_db_password"),
        AUTH_SECRET_KEY=SecretStr("sensitive_jwt_secret"),
        DATABASE_URL="postgresql+psycopg://app_user:sensitive_db_password@localhost:5432/knovera",
    )
    rep = repr(s)
    assert "sensitive_db_password" not in rep
    assert "sensitive_jwt_secret" not in rep
    assert "safe_database_uri" in rep
    assert "app_user" in rep

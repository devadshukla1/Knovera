"""Alembic environment configuration for Knovera.

Loads target metadata from backend.app.db.base.Base and connects using
the application's SQLAlchemy database URI.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure workspace root and backend are on sys.path
backend_dir = Path(__file__).resolve().parents[1]
root_dir = Path(__file__).resolve().parents[2]
for path_dir in [str(root_dir), str(backend_dir)]:
    if path_dir not in sys.path:
        sys.path.insert(0, path_dir)

from backend.app.core.config import get_settings
from backend.app.db.base import Base
import backend.app.models  # noqa: F401 - Register models with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# Inject configured database URI
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_uri)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without an active DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a live DB connection."""
    connect_args = (
        {"connect_timeout": 3}
        if settings.sqlalchemy_database_uri.startswith("postgresql")
        else {}
    )
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

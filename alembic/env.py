"""Alembic migration environment.

Reads DATABASE_URL from the environment (or falls back to alembic.ini)
so migrations work identically in local dev, staging, and production.
"""

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Alembic Config object — access to values in the .ini file.
config = context.config

# Set up loggers from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from DATABASE_URL env var if present.
# NOTE: We escape '%' → '%%' because config.set_main_option() routes through
# Python's configparser which treats bare '%' as interpolation syntax.
# (e.g. '%40' in a URL-encoded password would be mis-parsed as %(40)s)
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

# Import models so autogenerate can detect schema changes.
# Uncomment target_metadata when you want autogenerate support.
# from app.models import Base
# target_metadata = Base.metadata
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live connection)."""
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
    """Run migrations in 'online' mode — bypasses configparser for URL safety.

    We create the engine directly from the raw DATABASE_URL env var (or the
    already-set config option) to avoid any configparser % re-interpretation
    that would corrupt URL-encoded characters in the connection string.
    """
    # Prefer the raw env var to avoid double-unescaping through configparser
    url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

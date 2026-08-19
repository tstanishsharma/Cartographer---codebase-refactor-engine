"""
Alembic Migration Environment — Cartographer.

Configures Alembic to use the sync psycopg2 driver for migrations
(asyncpg cannot be used with Alembic's synchronous migration runner).

All ORM models are imported via app.db.models so Alembic autogenerate
can detect schema changes.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import all models for autogenerate detection
import app.db.models  # noqa: F401
from app.db.base import Base

# Alembic Config object from alembic.ini
config = context.config

# Set up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the sync DB URL for migrations built dynamically by config
from app.core.config import get_settings
settings = get_settings()
alembic_url = settings.alembic_database_url
config.set_main_option("sqlalchemy.url", alembic_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (no live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode (with live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

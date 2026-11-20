"""Alembic environment.

The synchronous migration URL is resolved in priority order:
  1. ``DATABASE_URL_SYNC`` env var (explicit sync URL, used by docker-compose
     and local dev), normalized to the psycopg2 driver;
  2. otherwise derived from ``DATABASE_URL`` (what Render injects, a
     ``postgres://`` async string) via ``app.core.config.to_sync_url``.

This means migrations run against the *same* database the app uses — including
on Render, where only ``DATABASE_URL`` is supplied — rather than falling back to
a localhost default.

Autogenerate is supported: `alembic revision --autogenerate -m "msg"`.
The very first migration (0001_initial) reflects the full SQLAlchemy
metadata so `alembic upgrade head` builds the schema from a fresh database.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app.*` importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings, to_sync_url  # noqa: E402
from app.database.base import Base  # noqa: E402
from app import models  # noqa: F401,E402  (registers all tables on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Derive the synchronous migration URL. Render injects DATABASE_URL only
# (a `postgres://` async string) and does NOT provide DATABASE_URL_SYNC, so we
# must derive the psycopg2 sync URL from DATABASE_URL when the explicit sync
# var is absent. See app.core.config.to_sync_url for the driver normalization.
sync_url = os.environ.get("DATABASE_URL_SYNC")
if not sync_url:
    sync_url = to_sync_url(os.environ.get("DATABASE_URL") or settings.database_url)
else:
    sync_url = to_sync_url(sync_url)
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url, target_metadata=target_metadata, literal_binds=True,
        compare_type=True, compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            compare_type=True, compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""Safety guard for destructive test-database operations.

The PostgreSQL integration fixtures drop and recreate all application tables.
That is only safe against a database explicitly designated for testing. This
module enforces three conditions before any destructive operation proceeds:

  1. an explicit opt-in via the ``ALLOW_DESTRUCTIVE_TEST_DB`` environment
     variable (set to ``1``);
  2. the connection URL actually names a database;
  3. the database name (or host) clearly identifies a test database
     (contains the marker ``test``).

If any condition fails, a :class:`RuntimeError` is raised — refusing to touch
what might be a production or staging database. The guard is a pure function so
it can be unit-tested without a live database.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

# Environment variable that must be set to "1" to allow destructive setup.
OPT_IN_ENV = "ALLOW_DESTRUCTIVE_TEST_DB"

# Substrings that clearly mark a database or host as a test database.
_TEST_MARKERS = ("test",)


def _db_name_and_host(url: str) -> tuple[str, str]:
    """Return (database_name, host) lowercased from a SQLAlchemy/Postgres URL."""
    # Strip the SQLAlchemy +driver suffix so urlparse parses the scheme.
    clean = url.replace("+asyncpg", "").replace("+psycopg2", "")
    parsed = urlparse(clean)
    db_name = (parsed.path or "").lstrip("/").lower()
    host = (parsed.hostname or "").lower()
    return db_name, host


def assert_destructive_test_database_allowed(url: str) -> None:
    """Raise ``RuntimeError`` unless ``url`` is an explicitly-designated test DB.

    Called by the PostgreSQL test fixtures before ``drop_all``/``create_all``.
    """
    if not url:
        raise RuntimeError(
            "Refusing destructive test setup: DATABASE_URL is not set."
        )
    if os.environ.get(OPT_IN_ENV) != "1":
        raise RuntimeError(
            f"Refusing destructive test setup: set {OPT_IN_ENV}=1 to opt in to "
            "dropping/recreating tables on the test database."
        )
    db_name, host = _db_name_and_host(url)
    if not db_name:
        raise RuntimeError(
            f"Refusing destructive test setup: URL {url!r} has no database name."
        )
    if not any(marker in db_name or marker in host for marker in _TEST_MARKERS):
        raise RuntimeError(
            f"Refusing destructive test setup against database {db_name!r} on host "
            f"{host!r}: the database name or host must clearly indicate a test "
            "database (contain 'test')."
        )

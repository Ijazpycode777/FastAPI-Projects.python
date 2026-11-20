"""Targeted regression tests for the follow-up correction pass.

Covers (SQLite-runnable, no live Postgres needed):
  * `to_sync_url` migration URL derivation (#1)
  * the destructive-test-database safety guard (#5)
  * failed-login persistence, lockout threshold, lock expiry (#2)
  * SlowAPI rate limiting on /api/v1/auth/login (#2)
  * SPA fallback: trailing-slash API/health, bare /api, encoded path
    traversal, normal frontend routes, existing/missing assets (#3)
"""
from __future__ import annotations

import os
import shutil
import tempfile
import logging
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings, to_sync_url
from app.core.limiter import limiter
from app.database.safety import assert_destructive_test_database_allowed
from app.database.session import get_db
from app.main import create_app
from app.models.user import User
from app.security.password import hash_password, verify_password
from sqlalchemy.ext.asyncio import async_sessionmaker


# ---------------------------------------------------------------------------
# #1 — to_sync_url (migration URL derivation)
# ---------------------------------------------------------------------------
def test_to_sync_url_render_postgres_scheme():
    assert to_sync_url("postgres://u:p@host:5432/db") == "postgresql+psycopg2://u:p@host:5432/db"


def test_to_sync_url_asyncpg_to_psycopg2():
    assert to_sync_url("postgresql+asyncpg://u:p@host:5432/db") == "postgresql+psycopg2://u:p@host:5432/db"


def test_to_sync_url_bare_postgresql():
    assert to_sync_url("postgresql://u:p@host:5432/db") == "postgresql+psycopg2://u:p@host:5432/db"


def test_to_sync_url_already_psycopg2_unchanged():
    assert to_sync_url("postgresql+psycopg2://u:p@host:5432/db") == "postgresql+psycopg2://u:p@host:5432/db"


def test_to_sync_url_sqlite_unchanged():
    assert to_sync_url("sqlite:///./test.db") == "sqlite:///./test.db"


def test_to_sync_url_empty():
    assert to_sync_url("") == ""


# ---------------------------------------------------------------------------
# #5 — safety guard (no live DB needed)
# ---------------------------------------------------------------------------
def test_guard_refuses_empty_url(monkeypatch):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TEST_DB", "1")
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        assert_destructive_test_database_allowed("")


def test_guard_refuses_without_opt_in(monkeypatch):
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_TEST_DB", raising=False)
    with pytest.raises(RuntimeError, match="ALLOW_DESTRUCTIVE_TEST_DB=1"):
        assert_destructive_test_database_allowed("postgresql+asyncpg://u@h/smartcampus_test")


def test_guard_refuses_non_test_database_name(monkeypatch):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TEST_DB", "1")
    with pytest.raises(RuntimeError, match="must clearly indicate a test database"):
        assert_destructive_test_database_allowed("postgresql+asyncpg://u@h/smartcampus")


def test_guard_refuses_missing_db_name(monkeypatch):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TEST_DB", "1")
    with pytest.raises(RuntimeError, match="no database name"):
        assert_destructive_test_database_allowed("postgresql+asyncpg://u@h/")


def test_guard_allows_explicit_test_database(monkeypatch):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TEST_DB", "1")
    # Should not raise.
    assert_destructive_test_database_allowed("postgresql+asyncpg://u@localhost:5433/smartcampus_test")


def test_guard_allows_test_host(monkeypatch):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TEST_DB", "1")
    assert_destructive_test_database_allowed("postgresql+asyncpg://u@test-host.example/db")


# ---------------------------------------------------------------------------
# fixtures for auth + SPA tests
# ---------------------------------------------------------------------------
async def _make_user(db, email="lock@test.edu", password="GoodPass!2025", role="admin"):
    u = User(email=email, role=role, password_hash=hash_password(password),
             full_name="Lock Test", is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# #2 — failed-login persistence, lockout, lock expiry
# ---------------------------------------------------------------------------
async def test_failed_login_attempt_persists(client, db):
    u = await _make_user(db)
    resp = await client.post("/api/v1/auth/login", json={
        "email": "lock@test.edu", "password": "WrongPass!2025",
    })
    assert resp.status_code == 401
    await db.refresh(u)
    # The counter MUST persist despite the auth error (commit before raise).
    assert u.failed_login_attempts == 1


async def test_account_locks_after_threshold(client, db, monkeypatch):
    monkeypatch.setattr(settings, "account_lockout_threshold", 3)
    u = await _make_user(db)
    for _ in range(3):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "lock@test.edu", "password": "WrongPass!2025",
        })
        assert resp.status_code == 401
    await db.refresh(u)
    assert u.locked_until is not None
    locked = datetime.fromisoformat(u.locked_until)
    assert locked.tzinfo is not None, "lockout timestamp must be timezone-aware"
    assert locked > datetime.now(timezone.utc), "lockout must be a real FUTURE time"
    # A valid password is still rejected while locked.
    resp = await client.post("/api/v1/auth/login", json={
        "email": "lock@test.edu", "password": "GoodPass!2025",
    })
    assert resp.status_code == 401
    assert "lock" in resp.json()["error"]["message"].lower()


async def test_login_available_again_after_lock_expires(client, db, monkeypatch):
    monkeypatch.setattr(settings, "account_lockout_threshold", 3)
    u = await _make_user(db)
    for _ in range(3):
        await client.post("/api/v1/auth/login", json={
            "email": "lock@test.edu", "password": "WrongPass!2025",
        })
    await db.refresh(u)
    assert u.locked_until is not None
    # Simulate the lockout elapsing: push locked_until into the past.
    u.locked_until = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    await db.commit()
    resp = await client.post("/api/v1/auth/login", json={
        "email": "lock@test.edu", "password": "GoodPass!2025",
    })
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# #2 — SlowAPI rate limiting on the login endpoint
# ---------------------------------------------------------------------------
async def test_login_rate_limit_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "login_rate_limit", "3/minute")
    # Clear any leftover counters so the test is deterministic.
    try:
        limiter._storage.reset()
    except Exception:  # pragma: no cover - storage API safety net
        pass
    # Three attempts are allowed (auth failures, but under the limit)...
    for _ in range(3):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@test.edu", "password": "Whatever!2025",
        })
        assert resp.status_code == 401
    # ...the fourth from the same IP is rate-limited.
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nobody@test.edu", "password": "Whatever!2025",
    })
    assert resp.status_code == 429, resp.text


# ---------------------------------------------------------------------------
# #3 — SPA fallback (trailing-slash API, traversal, assets)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def spa_client(test_engine):
    """Fresh app with a temp built-frontend dist, SQLite get_db override."""
    tmpdist = tempfile.mkdtemp(prefix="sc_spa_")
    with open(os.path.join(tmpdist, "index.html"), "w") as f:
        f.write("<!doctype html><html><body>SPA-SHELL</body></html>")
    os.makedirs(os.path.join(tmpdist, "assets"), exist_ok=True)
    with open(os.path.join(tmpdist, "assets", "app.js"), "w") as f:
        f.write("// bundle")
    os.environ["FRONTEND_DIST_DIR"] = tmpdist
    try:
        fresh_app = create_app()
    finally:
        os.environ.pop("FRONTEND_DIST_DIR", None)

    Session = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)

    async def _override():
        async with Session() as session:
            yield session

    fresh_app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=fresh_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    fresh_app.dependency_overrides.clear()
    shutil.rmtree(tmpdist, ignore_errors=True)


def _is_json(resp) -> bool:
    return resp.headers.get("content-type", "").startswith("application/json")


async def test_spa_api_unknown_trailing_slash_json_404(spa_client):
    resp = await spa_client.get("/api/v1/unknown/")
    assert resp.status_code == 404
    assert _is_json(resp)
    assert "SPA-SHELL" not in resp.text


async def test_spa_health_trailing_slash_json_404(spa_client):
    resp = await spa_client.get("/health/")
    assert resp.status_code == 404
    assert _is_json(resp)
    assert "SPA-SHELL" not in resp.text


async def test_spa_bare_api_json_404(spa_client):
    resp = await spa_client.get("/api")
    assert resp.status_code == 404
    assert _is_json(resp)
    assert "SPA-SHELL" not in resp.text


async def test_spa_encoded_path_traversal_rejected(spa_client):
    # %2e%2e -> ".." ; Starlette decodes the path before the catch-all sees it,
    # so this resolves to a path OUTSIDE the dist directory and must be 404
    # (never the SPA shell, never a file from elsewhere on disk).
    resp = await spa_client.get("/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd")
    assert resp.status_code == 404
    assert "root:" not in resp.text
    assert "SPA-SHELL" not in resp.text


async def test_spa_normal_frontend_route_returns_shell(spa_client):
    resp = await spa_client.get("/students")
    assert resp.status_code == 200
    assert "SPA-SHELL" in resp.text


async def test_spa_existing_asset_served(spa_client):
    resp = await spa_client.get("/assets/app.js")
    assert resp.status_code == 200
    assert "bundle" in resp.text


async def test_spa_missing_asset_returns_404(spa_client):
    resp = await spa_client.get("/assets/missing.js")
    assert resp.status_code == 404
    assert "SPA-SHELL" not in resp.text


# ---------------------------------------------------------------------------
# #4 — bootstrap password policy (warnings, never fatal) — unit
# ---------------------------------------------------------------------------
def test_bootstrap_warns_on_default_password_in_production(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "seed_admin_password", "ChangeMe!2025")
    from app.seed import _check_admin_password_policy
    with caplog.at_level(logging.WARNING, logger="smartcampus.seed"):
        _check_admin_password_policy("ChangeMe!2025")  # must NOT raise
    assert any("built-in default" in r.message for r in caplog.records)


def test_bootstrap_warns_on_weak_password_in_production(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")
    from app.seed import _check_admin_password_policy
    with caplog.at_level(logging.WARNING, logger="smartcampus.seed"):
        _check_admin_password_policy("short1")  # must NOT raise
    assert any("weak" in r.message for r in caplog.records)


def test_bootstrap_silent_on_default_password_in_dev(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "development")
    from app.seed import _check_admin_password_policy
    with caplog.at_level(logging.WARNING, logger="smartcampus.seed"):
        _check_admin_password_policy("ChangeMe!2025")  # no warning, no raise
    assert not any("built-in default" in r.message for r in caplog.records)

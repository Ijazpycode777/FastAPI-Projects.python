"""PostgreSQL + asyncpg integration tests.

These tests run ONLY against a real PostgreSQL database (set DATABASE_URL to a
postgresql+asyncpg URL in the environment). They exist because several bugs —
notably sqlalchemy.exc.MissingGreenlet from lazy relationship access under
async, and advisory-lock seeding coordination — do NOT reproduce under
aiosqlite/SQLite, so the SQLite suite cannot validate them.

Run from backend/ with:

    DATABASE_URL=postgresql+asyncpg://smartcampus@localhost:5433/smartcampus \\
    DATABASE_URL_SYNC=postgresql+psycopg2://smartcampus@localhost:5433/smartcampus \\
    SESSION_COOKIE_SECURE=false SEED_RESET_ON_START=true \\
    python -m pytest tests/integration/test_postgres_workflows.py -v
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.base import Base
from app.database.session import get_db
from app.main import create_app
from app.models.user import User

PG_URL = os.environ.get("DATABASE_URL", "")
IS_PG = PG_URL.startswith("postgresql") or PG_URL.startswith("postgres")
pytestmark = pytest.mark.skipif(
    not IS_PG, reason="PostgreSQL integration tests need DATABASE_URL=postgresql+asyncpg://..."
)


async def _truncate_all(engine) -> None:
    """Drop & recreate all tables from metadata (clean slate per test)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture
async def pg_engine():
    # The module-level engine (used by seed_demo_data via AsyncSessionLocal)
    # holds asyncpg connections bound to whichever event loop last used them.
    # pytest-asyncio gives each test its own loop, so dispose it here (and at
    # teardown) to clear loop-bound connections and avoid "Event loop is closed".
    from app.database import session as session_module
    await session_module.engine.dispose()
    engine = create_async_engine(PG_URL, future=True, pool_pre_ping=True)
    await _truncate_all(engine)
    yield engine
    await _truncate_all(engine)
    await engine.dispose()
    await session_module.engine.dispose()


@pytest_asyncio.fixture
async def pg_db(pg_engine):
    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def pg_client(pg_engine):
    """Async HTTP client bound to a Postgres-backed get_db override."""
    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    from app.main import app

    async def _override():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Seeding completes on Postgres (Issue A — MissingGreenlet)
# ---------------------------------------------------------------------------
async def test_seed_completes_without_missing_greenlet(pg_engine):
    from app.seed import seed_demo_data

    await seed_demo_data()  # must NOT raise MissingGreenlet on asyncpg

    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
    async with Session() as db:
        admins = (await db.execute(select(User).where(User.role == "admin"))).scalars().all()
        teachers = (await db.execute(select(User).where(User.role == "teacher"))).scalars().all()
        students = (await db.execute(select(User).where(User.role == "student"))).scalars().all()
    assert any(a.email == "admin@smartcampus.edu" for a in admins)
    assert len(admins) == 1, "seeding must not create duplicate admins"
    assert len(teachers) == 1
    assert len(students) == 3


# ---------------------------------------------------------------------------
# 2. Seeding is safe under concurrent (multi-worker) invocation (Issue B)
# ---------------------------------------------------------------------------
async def test_concurrent_seeding_is_safe(pg_engine):
    from app.seed import seed_demo_data

    # Two "workers" seed at the same time. The advisory lock must serialize them:
    # one seeds, the other skips; no duplicates, no IntegrityError.
    results = await asyncio.gather(
        seed_demo_data(), seed_demo_data(), return_exceptions=True
    )
    assert all(not isinstance(r, Exception) for r in results), results

    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
    async with Session() as db:
        admin_count = (await db.execute(
            select(User).where(User.email == "admin@smartcampus.edu")
        )).scalars().all()
    assert len(admin_count) == 1, "concurrent seeding duplicated the admin"


# ---------------------------------------------------------------------------
# 3 & 4. Administrator login succeeds; invalid credentials rejected (Issue C)
# ---------------------------------------------------------------------------
async def test_login_succeeds_with_seeded_admin(pg_client):
    from app.seed import seed_demo_data
    await seed_demo_data()

    resp = await pg_client.post("/api/v1/auth/login", json={
        "email": "admin@smartcampus.edu", "password": "ChangeMe!2025",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == "admin@smartcampus.edu"
    assert body["user"]["role"] == "admin"
    # Session cookie must be set (httpx Cookies supports `in` by name).
    assert "smartcampus_session" in pg_client.cookies

    me = await pg_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "admin@smartcampus.edu"


async def test_login_rejects_invalid_credentials(pg_client):
    from app.seed import seed_demo_data
    await seed_demo_data()

    resp = await pg_client.post("/api/v1/auth/login", json={
        "email": "admin@smartcampus.edu", "password": "wrong-password",
    })
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# 5. Role-based access restrictions (RBAC)
# ---------------------------------------------------------------------------
async def test_student_cannot_access_admin_endpoint(pg_client):
    from app.seed import seed_demo_data
    await seed_demo_data()

    await pg_client.post("/api/v1/auth/login", json={
        "email": "student.ali@smartcampus.edu", "password": "Student!2025",
    })
    # /api/v1/students requires admin.
    resp = await pg_client.get("/api/v1/students")
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_can_access_admin_endpoint(pg_client):
    from app.seed import seed_demo_data
    await seed_demo_data()
    await pg_client.post("/api/v1/auth/login", json={
        "email": "admin@smartcampus.edu", "password": "ChangeMe!2025",
    })
    resp = await pg_client.get("/api/v1/students")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json()["items"], list)


# ---------------------------------------------------------------------------
# 6. Main endpoints return appropriate responses (auth required)
# ---------------------------------------------------------------------------
async def test_unauthenticated_blocked_from_protected_endpoint(pg_client):
    resp = await pg_client.get("/api/v1/students")
    assert resp.status_code == 401


async def test_api_miss_returns_json_404_with_request_id(pg_client):
    # An unregistered /api path must return a JSON 404 (not the SPA shell).
    resp = await pg_client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"
    # RequestIdMiddleware must populate the request id (Issue E).
    assert body["error"]["request_id"]


# ---------------------------------------------------------------------------
# 7. Login works even when the static SPA mount is present (no API shadowing)
# ---------------------------------------------------------------------------
async def test_login_with_static_mount_present(pg_engine):
    """Reproduce production: built frontend served at / alongside the API.
    Login must still hit the API route (200), and an API miss must be JSON 404,
    not index.html."""
    from app.seed import seed_demo_data
    await seed_demo_data()

    tmpdist = tempfile.mkdtemp(prefix="sc_dist_")
    try:
        with open(os.path.join(tmpdist, "index.html"), "w") as f:
            f.write("<!doctype html><html><body>SPA</body></html>")
        os.makedirs(os.path.join(tmpdist, "assets"), exist_ok=True)
        with open(os.path.join(tmpdist, "assets", "app.js"), "w") as f:
            f.write("// bundle")

        os.environ["FRONTEND_DIST_DIR"] = tmpdist
        try:
            app = create_app()
        finally:
            os.environ.pop("FRONTEND_DIST_DIR", None)

        Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)

        async def _override():
            async with Session() as session:
                yield session

        app.dependency_overrides[get_db] = _override
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            login = await ac.post("/api/v1/auth/login", json={
                "email": "admin@smartcampus.edu", "password": "ChangeMe!2025",
            })
            assert login.status_code == 200, login.text
            assert login.json()["user"]["role"] == "admin"

            # SPA shell served for the root GET.
            root = await ac.get("/")
            assert root.status_code == 200
            assert "SPA" in root.text

            # An asset is served.
            asset = await ac.get("/assets/app.js")
            assert asset.status_code == 200

            # An API miss is a JSON 404, NOT the SPA shell.
            miss = await ac.get("/api/v1/does-not-exist")
            assert miss.status_code == 404
            assert miss.json()["error"]["code"] == "NOT_FOUND"
        app.dependency_overrides.clear()
    finally:
        shutil.rmtree(tmpdist, ignore_errors=True)

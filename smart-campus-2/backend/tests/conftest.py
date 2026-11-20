"""Pytest configuration: in-memory SQLite for tests, CSRF bypassed, app wired.

Tests never touch production data. A fresh SQLite DB is created per test
from the SQLAlchemy metadata (the same models used in Postgres).
"""
from __future__ import annotations

import os

# Force test settings BEFORE importing the app.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret-key")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite://")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://testserver")
os.environ.setdefault("SEED_RESET_ON_START", "false")
# Fast Argon2 params for the test suite (production keeps strong defaults).
os.environ.setdefault("ARGON2_TIME_COST", "1")
os.environ.setdefault("ARGON2_MEMORY_COST", "1024")
os.environ.setdefault("ARGON2_PARALLELISM", "1")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: F401,E402  (register tables)
from app.database.base import Base  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware import csrf as csrf_module  # noqa: E402

# Bypass CSRF in the test suite (CSRF logic is unit-tested separately where useful).
csrf_module.csrf_tokens_match = lambda a, b: True


@pytest_asyncio.fixture
async def test_engine():
    """Per-test in-memory SQLite engine bound to the test's own event loop."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _session_factory(engine):
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def db(test_engine):
    async with _session_factory(test_engine)() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    Session = _session_factory(test_engine)

    async def _override():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db):
    """Create an admin and yield (user, plain_password)."""
    from app.security.password import hash_password
    from app.models.user import User
    u = User(email="admin@test.edu", role="admin",
             password_hash=hash_password("AdminPass!2025"),
             full_name="Test Admin", is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def admin_client(client, admin_user):
    """An async client already logged in as admin."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.edu", "password": "AdminPass!2025"
    })
    assert resp.status_code == 200, resp.text
    return client


@pytest_asyncio.fixture
async def academic_setup(admin_client):
    """Create a coherent academic structure via the API; return a dict of IDs."""
    sess = await admin_client.post("/api/v1/sessions", json={
        "name": "2025-2026", "start_date": "2025-08-01", "end_date": "2026-05-31", "is_active": True,
    })
    assert sess.status_code == 200, sess.text
    prog = await admin_client.post("/api/v1/programs", json={"code": "ICS", "name": "ICS"})
    assert prog.status_code == 200, prog.text
    cls = await admin_client.post("/api/v1/classes", json={
        "program_id": prog.json()["id"], "name": "Part 1", "year": 1,
    })
    assert cls.status_code == 200, cls.text
    sec = await admin_client.post("/api/v1/sections", json={
        "class_level_id": cls.json()["id"], "name": "A", "capacity": 40,
    })
    assert sec.status_code == 200, sec.text
    subj = await admin_client.post("/api/v1/subjects", json={
        "program_id": prog.json()["id"], "code": "CS", "name": "Computer Science",
    })
    assert subj.status_code == 200, subj.text
    room = await admin_client.post("/api/v1/classrooms", json={"room_number": "101", "capacity": 40})
    assert room.status_code == 200, room.text
    return {
        "session_id": sess.json()["id"],
        "program_id": prog.json()["id"],
        "class_id": cls.json()["id"],
        "section_id": sec.json()["id"],
        "subject_id": subj.json()["id"],
        "classroom_id": room.json()["id"],
    }


async def login_as(client, email: str, password: str):
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return client

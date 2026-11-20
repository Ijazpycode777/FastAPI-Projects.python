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
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import create_app
from app.models.user import User
from app.seed import _SEED_ADVISORY_KEY

PG_URL = os.environ.get("DATABASE_URL", "")
IS_PG = PG_URL.startswith("postgresql") or PG_URL.startswith("postgres")
pytestmark = pytest.mark.skipif(
    not IS_PG, reason="PostgreSQL integration tests need DATABASE_URL=postgresql+asyncpg://..."
)


async def _truncate_all(engine) -> None:
    """Drop & recreate all tables from metadata (clean slate per test).

    Guarded by ``assert_destructive_test_database_allowed`` — see the fixture.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture
async def pg_engine():
    # The module-level engine (used by seed_demo_data via AsyncSessionLocal)
    # holds asyncpg connections bound to whichever event loop last used them.
    # pytest-asyncio gives each test its own loop, so dispose it here (and at
    # teardown) to clear loop-bound connections and avoid "Event loop is closed".
    # SAFETY: refuse to drop/recreate tables unless DATABASE_URL points at an
    # explicitly-designated test database AND the operator opted in. This
    # protects against accidentally pointing the suite at a production DB.
    from app.database.safety import assert_destructive_test_database_allowed

    assert_destructive_test_database_allowed(PG_URL)
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


# ===========================================================================
# Follow-up audit regressions
# ===========================================================================


async def _fresh_engine_acquires_lock() -> bool:
    """A brand-new engine (its own connections) tries the advisory lock."""
    eng = create_async_engine(PG_URL, pool_pre_ping=True)
    try:
        async with eng.connect() as conn:
            got = bool((await conn.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": _SEED_ADVISORY_KEY}
            )).scalar_one())
            if got:
                await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _SEED_ADVISORY_KEY})
            return got
    finally:
        await eng.dispose()


# ---------------------------------------------------------------------------
# V1. Lock released after successful seeding
# ---------------------------------------------------------------------------
async def test_lock_released_after_successful_seeding(pg_engine):
    from app.seed import seed_demo_data
    await seed_demo_data()
    assert await _fresh_engine_acquires_lock(), "advisory lock leaked after success"


# ---------------------------------------------------------------------------
# V2. Lock released after a seeding exception
# ---------------------------------------------------------------------------
async def test_lock_released_after_seeding_exception(pg_engine):
    import app.seed as seed_mod
    from app.seed import seed_demo_data
    orig = seed_mod.enter_marks

    async def boom(*a, **kw):
        raise RuntimeError("simulated failure mid-seed")

    seed_mod.enter_marks = boom
    try:
        with pytest.raises(RuntimeError):
            await seed_demo_data()
    finally:
        seed_mod.enter_marks = orig
    assert await _fresh_engine_acquires_lock(), "advisory lock leaked after exception"


# ---------------------------------------------------------------------------
# V3. Two workers seed simultaneously (no duplicates)
# ---------------------------------------------------------------------------
async def test_two_workers_seed_simultaneously(pg_engine):
    from app.seed import seed_demo_data
    results = await asyncio.gather(seed_demo_data(), seed_demo_data(), return_exceptions=True)
    assert all(not isinstance(r, Exception) for r in results), results
    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
    async with Session() as db:
        admins = (await db.execute(select(User).where(User.role == "admin"))).scalars().all()
    assert len(admins) == 1


# ---------------------------------------------------------------------------
# V4. Uniqueness conflict inside _get_or_create does not abort outer transaction
# ---------------------------------------------------------------------------
async def test_uniqueness_conflict_keeps_outer_transaction_usable(pg_engine):
    from app.seed import _get_or_create
    from app.security.password import hash_password

    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
    async with Session() as db:
        existing = User(email="dup@test.edu", role="admin",
                        password_hash=hash_password("P@ssw0rd!1"), full_name="Dup", is_active=True)
        db.add(existing)
        await db.commit()

    async with Session() as db:
        other = User(email="other@test.edu", role="admin",
                     password_hash=hash_password("P@ssw0rd!1"), full_name="Other", is_active=True)
        db.add(other)
        await db.flush()  # pending work in the outer transaction
        # Force a conflicting insert.
        got = await _get_or_create(
            db, User, [User.email == "dup@test.edu"],
            email="dup@test.edu", role="admin",
            password_hash=hash_password("X@ssw0rd!1"), full_name="Dup2", is_active=True,
        )
        assert got.email == "dup@test.edu"
        # Outer transaction must still be usable (SAVEPOINT contained the error).
        rows = (await db.execute(select(User))).scalars().all()
        await db.commit()
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# V5. Bootstrap re-syncs the existing admin's password to SEED_ADMIN_PASSWORD
# ---------------------------------------------------------------------------
async def test_bootstrap_resyncs_existing_admin_password(pg_engine, monkeypatch):
    from app.seed import bootstrap_admin

    monkeypatch.setattr(settings, "seed_admin_email", "keep@test.edu")
    monkeypatch.setattr(settings, "seed_admin_password", "FirstPass!2025")
    assert await bootstrap_admin() is True

    # Restart with a DIFFERENT configured password: the permanent admin must be
    # re-synced so the NEW env password ALWAYS works (restarts are destructive
    # for this account by design — it is the permanent access account).
    monkeypatch.setattr(settings, "seed_admin_password", "SecondPass!2025")
    assert await bootstrap_admin() is True

    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
    async with Session() as db:
        admins = (await db.execute(select(User).where(User.email == "keep@test.edu"))).scalars().all()
    assert len(admins) == 1, "bootstrap must not duplicate the admin"

    from app.security.password import verify_password
    assert verify_password("FirstPass!2025", admins[0].password_hash) is False
    assert verify_password("SecondPass!2025", admins[0].password_hash) is True


# ---------------------------------------------------------------------------
# V6. Bootstrap creates an admin when none exists; idempotent
# ---------------------------------------------------------------------------
async def test_bootstrap_creates_admin_when_missing(pg_engine, monkeypatch):
    from app.seed import bootstrap_admin

    monkeypatch.setattr(settings, "seed_admin_email", "boot@test.edu")
    monkeypatch.setattr(settings, "seed_admin_password", "BootPass!2025")
    assert await bootstrap_admin() is True
    assert await bootstrap_admin() is True  # idempotent

    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
    async with Session() as db:
        admins = (await db.execute(select(User).where(User.email == "boot@test.edu"))).scalars().all()
    assert len(admins) == 1


async def test_bootstrap_rejects_wrong_role_account(pg_engine, monkeypatch):
    """If SEED_ADMIN_EMAIL belongs to a teacher/student, bootstrap must NOT
    report success and must NOT modify that account (no promotion, no password
    reset)."""
    from app.seed import bootstrap_admin
    from app.security.password import hash_password, verify_password

    monkeypatch.setattr(settings, "seed_admin_email", "teacher@boot.test")
    monkeypatch.setattr(settings, "seed_admin_password", "NewAdminPass!2025")
    # Pre-create a TEACHER account at the configured email.
    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
    async with Session() as db:
        from app.models.user import User
        t = User(email="teacher@boot.test", role="teacher",
                 password_hash=hash_password("TeacherPass!2025"),
                 full_name="Boot Teacher", is_active=True)
        db.add(t)
        await db.commit()

    # Bootstrap must report not-usable (False) for a non-admin account.
    assert await bootstrap_admin() is False

    # The teacher account is untouched: still role=teacher, same password,
    # no second account created.
    async with Session() as db:
        rows = (await db.execute(select(User).where(User.email == "teacher@boot.test"))).scalars().all()
    assert len(rows) == 1
    t = rows[0]
    assert t.role == "teacher"
    assert verify_password("TeacherPass!2025", t.password_hash) is True
    assert verify_password("NewAdminPass!2025", t.password_hash) is False


async def test_bootstrap_created_admin_has_admin_role_and_active(pg_engine, monkeypatch):
    """A freshly bootstrapped admin must have role='admin' and is_active=True."""
    from app.seed import bootstrap_admin

    monkeypatch.setattr(settings, "seed_admin_email", "fresh@test.edu")
    monkeypatch.setattr(settings, "seed_admin_password", "FreshPass!2025")
    assert await bootstrap_admin() is True
    Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
    async with Session() as db:
        admin = (await db.execute(select(User).where(User.email == "fresh@test.edu"))).scalar_one()
    assert admin.role == "admin"
    assert admin.is_active is True
    assert admin.must_reset_password is False


# ---------------------------------------------------------------------------
# V7. Demo material PDF exists and downloads
# ---------------------------------------------------------------------------
async def test_demo_material_pdf_downloads(pg_client):
    from app.seed import seed_demo_data
    await seed_demo_data()
    await pg_client.post("/api/v1/auth/login", json={
        "email": settings.seed_admin_email, "password": settings.seed_admin_password,
    })
    mats = (await pg_client.get("/api/v1/materials")).json()
    assert mats, "seed must create at least one study material"
    mat = mats[0]
    dl = await pg_client.get(f"/api/v1/materials/{mat['id']}/download")
    assert dl.status_code == 200, dl.text
    assert dl.headers["content-type"] == "application/pdf"
    body = dl.content
    assert body[:5] == b"%PDF-", "downloaded file must be a real PDF"
    assert len(body) > 100


# ---------------------------------------------------------------------------
# V8–V15. SPA fallback HTTP behavior (with a built frontend present)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def dist_client(pg_engine):
    """A client against a FRESH app with a temp built-frontend dist, bound to
    the Postgres get_db override. Exercises the real SPA-fallback route."""
    tmpdist = tempfile.mkdtemp(prefix="sc_dist_")
    try:
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

        Session = async_sessionmaker(bind=pg_engine, expire_on_commit=False)

        async def _override():
            async with Session() as session:
                yield session

        fresh_app.dependency_overrides[get_db] = _override
        transport = ASGITransport(app=fresh_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
        fresh_app.dependency_overrides.clear()
    finally:
        shutil.rmtree(tmpdist, ignore_errors=True)


async def test_spa_root_returns_index_html(dist_client):
    resp = await dist_client.get("/")
    assert resp.status_code == 200
    assert "SPA-SHELL" in resp.text


async def test_spa_unknown_frontend_route_returns_index_html(dist_client):
    # /students is a client-side route, not a backend route -> SPA shell.
    resp = await dist_client.get("/students")
    assert resp.status_code == 200
    assert "SPA-SHELL" in resp.text


async def test_spa_unknown_api_get_returns_json_404(dist_client):
    resp = await dist_client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
    assert "SPA-SHELL" not in resp.text


async def test_spa_unknown_api_post_returns_json_error_not_shell(dist_client):
    resp = await dist_client.post("/api/v1/does-not-exist", json={})
    assert resp.status_code in (404, 405)
    assert resp.headers["content-type"] == "application/json"
    assert "SPA-SHELL" not in resp.text


async def test_spa_health_does_not_return_index_html(dist_client):
    # /health is a registered route -> JSON, not the shell.
    resp = await dist_client.get("/health")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"
    assert "SPA-SHELL" not in resp.text
    # A near-miss of /health must be a JSON 404, not the shell.
    miss = await dist_client.get("/healthzzz")
    assert miss.status_code == 404
    assert "SPA-SHELL" not in miss.text


async def test_spa_docs_not_index_html(dist_client):
    miss = await dist_client.get("/docsxyz")
    assert miss.status_code == 404
    assert "SPA-SHELL" not in miss.text


async def test_spa_existing_asset_served(dist_client):
    resp = await dist_client.get("/assets/app.js")
    assert resp.status_code == 200
    assert "bundle" in resp.text


async def test_spa_missing_asset_returns_404(dist_client):
    resp = await dist_client.get("/assets/missing.js")
    assert resp.status_code == 404
    assert "SPA-SHELL" not in resp.text


async def test_spa_api_route_takes_precedence(dist_client):
    # /api/v1/students is a registered route requiring admin -> 401 (not shell).
    resp = await dist_client.get("/api/v1/students")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"

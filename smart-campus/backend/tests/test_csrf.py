"""End-to-end CSRF tests (real validation, NOT the suite-wide mock).

The default conftest bypasses CSRF (``csrf_tokens_match = lambda a, b: True``)
so endpoint tests can focus on behaviour. These tests use the ``real_csrf``
fixture to restore the real hmac-compare matcher and exercise the full
double-submit cookie flow against the actual CSRF middleware:

  * missing / invalid / valid token
  * stale (rotated) token rejected, fresh token accepted
  * no session (CSRF passes, auth fails) vs. wrong role (CSRF passes, authz fails)
  * the Secure attribute is scheme-aware (not set over HTTP, set behind an HTTPS proxy)
  * the exempt-path matcher is precise (no over-exemption)
  * Create program succeeds only with a valid token + admin session
"""
from __future__ import annotations

from app.middleware.csrf import is_exempt


def _csrf_payload(code: str = "PROG") -> dict:
    return {"code": code, "name": code}


async def _login(client, email: str, password: str):
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return client


def _csrf_token(client) -> str | None:
    return client.cookies.get("smartcampus_csrf")


# ---------------- token presence / validity ----------------

async def test_create_program_without_csrf_token_is_rejected(real_csrf, client, admin_user):
    """No X-CSRF-Token header → 403 CSRF_FAILED (the reported symptom)."""
    await _login(client, "admin@test.edu", "AdminPass!2025")
    resp = await client.post("/api/v1/programs", json=_csrf_payload())
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_FAILED"
    assert "CSRF" in resp.json()["error"]["message"]


async def test_create_program_with_invalid_csrf_token_is_rejected(real_csrf, client, admin_user):
    """Header present but wrong value → 403 CSRF_FAILED."""
    await _login(client, "admin@test.edu", "AdminPass!2025")
    resp = await client.post(
        "/api/v1/programs", json=_csrf_payload(),
        headers={"X-CSRF-Token": "bogus-token-does-not-match-cookie"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_FAILED"


async def test_create_program_with_valid_csrf_token_succeeds(real_csrf, client, admin_user):
    """Matching cookie + header + admin session → 200, program created."""
    await _login(client, "admin@test.edu", "AdminPass!2025")
    token = _csrf_token(client)
    assert token, "login must set the smartcampus_csrf cookie"
    resp = await client.post(
        "/api/v1/programs", json=_csrf_payload("VALID"),
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == "VALID"


# ---------------- token rotation ----------------

async def test_rotated_csrf_token_rejects_stale_and_accepts_fresh(real_csrf, client, admin_user):
    """After /auth/csrf rotates the cookie, a stale header is rejected but the fresh one works."""
    await _login(client, "admin@test.edu", "AdminPass!2025")
    stale = _csrf_token(client)
    assert stale

    rot = await client.post("/api/v1/auth/csrf")
    assert rot.status_code == 200
    fresh = rot.json()["csrf_token"]
    assert fresh != stale  # rotation produced a new token

    # Stale header vs fresh cookie → mismatch → 403
    resp = await client.post(
        "/api/v1/programs", json=_csrf_payload("STALE"),
        headers={"X-CSRF-Token": stale},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_FAILED"

    # Fresh header vs fresh cookie → match → 200
    resp = await client.post(
        "/api/v1/programs", json=_csrf_payload("FRESH"),
        headers={"X-CSRF-Token": fresh},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == "FRESH"


# ---------------- auth vs. CSRF ordering ----------------

async def test_valid_csrf_without_session_is_unauthenticated(real_csrf, client, admin_user):
    """CSRF check passes (valid cookie+header from /auth/csrf) but no session → 401.

    Proves CSRF runs before the route's auth dependency, and that a missing
    session surfaces as UNAUTHENTICATED — not as a CSRF error.
    """
    csrf_resp = await client.post("/api/v1/auth/csrf")
    token = csrf_resp.json()["csrf_token"]
    assert _csrf_token(client) == token  # cookie stored, no session cookie set

    resp = await client.post(
        "/api/v1/programs", json=_csrf_payload("NOSESS"),
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_student_with_valid_csrf_cannot_create_program(real_csrf, client, db):
    """CSRF passes but the role check rejects a student → 403 FORBIDDEN (not CSRF_FAILED)."""
    from app.models.user import User
    from app.security.password import hash_password
    u = User(email="student@test.edu", role="student",
             password_hash=hash_password("Student!2025"),
             full_name="Test Student", is_active=True)
    db.add(u)
    await db.commit()

    await _login(client, "student@test.edu", "Student!2025")
    token = _csrf_token(client)
    assert token

    resp = await client.post(
        "/api/v1/programs", json=_csrf_payload("ROLE"),
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code == 403
    # Role rejection, NOT a CSRF failure — the codes must differ.
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    assert resp.json()["error"]["code"] != "CSRF_FAILED"


# ---------------- scheme-aware Secure attribute ----------------

async def test_csrf_cookie_is_not_secure_over_http(real_csrf, client, admin_user):
    """Over plain HTTP the cookie must NOT carry Secure, or a browser drops it
    (the root cause of the reported 'CSRF token missing or invalid.' symptom).

    With the default dev config (csrf_secure=False) the cookie is never Secure,
    so it is always stored — including over HTTP.
    """
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.edu", "password": "AdminPass!2025",
    })
    cookies = resp.headers.get_list("set-cookie")
    csrf_cookie = next((c for c in cookies if c.startswith("smartcampus_csrf=")), None)
    assert csrf_cookie, "login must set the smartcampus_csrf cookie"
    assert "Secure" not in csrf_cookie, "over HTTP a Secure cookie would be dropped by the browser"


async def test_csrf_cookie_scheme_aware_when_csrf_secure_true(real_csrf, client, admin_user, monkeypatch):
    """The root-cause fix: with CSRF_SECURE=true (the render.yaml production setting),
    the Secure attribute is honored ONLY over HTTPS — never over HTTP.

    Without scheme-awareness, CSRF_SECURE=true over HTTP would mark the cookie
    Secure and a browser would drop it, so no csrf cookie would ever be stored
    and every mutation would fail with 'CSRF token missing or invalid.'
    """
    monkeypatch.setattr("app.core.config.settings.csrf_secure", True)

    # Over HTTP (even with csrf_secure=true): cookie must NOT be Secure.
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.edu", "password": "AdminPass!2025",
    })
    cookies = resp.headers.get_list("set-cookie")
    csrf_cookie = next((c for c in cookies if c.startswith("smartcampus_csrf=")), None)
    assert csrf_cookie
    assert "Secure" not in csrf_cookie, (
        "scheme-aware fix: even with CSRF_SECURE=true, a Secure cookie over HTTP "
        "would be dropped by the browser — must stay non-Secure over HTTP"
    )

    # Behind a TLS-terminating proxy (X-Forwarded-Proto: https): cookie IS Secure.
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.edu", "password": "AdminPass!2025",
    }, headers={"X-Forwarded-Proto": "https"})
    cookies = resp.headers.get_list("set-cookie")
    csrf_cookie = next((c for c in cookies if c.startswith("smartcampus_csrf=")), None)
    assert csrf_cookie
    assert "Secure" in csrf_cookie, "on HTTPS the cookie should honour the Secure flag"


# ---------------- exempt-path precision (unit) ----------------

def test_is_exempt_matches_precisely():
    """Exempt paths match exactly or as a true sub-path — never a bare prefix."""
    assert is_exempt("/api/v1/auth/login") is True
    assert is_exempt("/api/v1/auth/csrf") is True
    assert is_exempt("/api/v1/auth/login/sub") is True  # true sub-path
    # Over-exemption regression: a bare startswith would wrongly exempt these.
    assert is_exempt("/api/v1/auth/login-anything") is False
    assert is_exempt("/api/v1/auth/csrf-forged") is False
    # Real protected endpoints are not exempt.
    assert is_exempt("/api/v1/programs") is False
    assert is_exempt("/api/v1/students") is False

"""Server-managed browser sessions.

We store a cryptographically random session identifier in an HttpOnly cookie.
The full session record (user_id, role, issued_at, expires_at, revoked) is
persisted in PostgreSQL so sessions can be revoked server-side.

Token generation uses ``secrets.token_urlsafe`` (CSPRNG).

CSRF is implemented as a double-submit cookie: a non-HttpOnly CSRF cookie
holds a token that must also be sent in the ``X-CSRF-Token`` header on
state-changing requests. The session token itself never leaves the HttpOnly
cookie, so it cannot be read by JS and cannot be leaked via XSS.
"""
from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Response
from starlette.requests import Request

from app.core.config import settings


def generate_session_token() -> str:
    """CSPRNG 32-byte URL-safe token. ~256 bits of entropy."""
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def session_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=settings.session_max_age_seconds)


def _request_is_https(request: Request) -> bool:
    """True when the request reached the app over HTTPS (directly or via a TLS-terminating proxy).

    Browsers refuse to store a cookie carrying the ``Secure`` attribute when it
    is delivered over plain HTTP. The CSRF/session cookie ``Secure`` flag is
    therefore honored only when the connection is actually HTTPS — otherwise
    the cookie would be silently dropped and the double-submit CSRF flow would
    reject every state-changing request (the exact "CSRF token missing or
    invalid." symptom). Behind Render's TLS-terminating proxy the app reads
    ``X-Forwarded-Proto`` (uvicorn ``--proxy-headers``); the header is also
    checked directly so the detection is correct even without that flag.
    """
    if request.url.scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "")
    # X-Forwarded-Proto may be a comma-separated list when proxies are chained.
    return forwarded.split(",")[0].strip().lower() == "https"


def set_session_cookie(response: Response, token: str, expires_seconds: int, request: Request) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=expires_seconds,
        httponly=True,
        secure=settings.session_cookie_secure and _request_is_https(request),
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")


def set_csrf_cookie(response: Response, token: str, request: Request) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=False,  # JS must read it for double-submit
        secure=settings.csrf_secure and _request_is_https(request),
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def csrf_tokens_match(cookie_token: Optional[str], header_token: Optional[str]) -> bool:
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)

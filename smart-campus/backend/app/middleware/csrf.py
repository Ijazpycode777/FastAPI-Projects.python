"""CSRF protection middleware (double-submit cookie).

For every unsafe method (POST/PUT/PATCH/DELETE) we require:
  * a non-HttpOnly CSRF cookie ``smartcampus_csrf``
  * a matching ``X-CSRF-Token`` request header

The session token lives in a separate HttpOnly cookie and is never exposed
to JavaScript, so an attacker cannot forge both tokens via XSS. The
``SameSite=lax`` default also blocks most cross-site submissions.

Endpoints listed in ``_EXEMPT_PATHS`` (login, logout, csrf issuance) do not
require the header because no session exists yet.
"""
from __future__ import annotations

from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.security.sessions import csrf_tokens_match

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_EXEMPT_PREFIXES = (
    f"{settings.api_v1_prefix}/auth/login",
    f"{settings.api_v1_prefix}/auth/csrf",
    f"{settings.api_v1_prefix}/auth/password-reset",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def is_exempt(path: str, exempt: Iterable[str] = _EXEMPT_PREFIXES) -> bool:
    # Exact match or a true sub-path (trailing slash). A bare startswith(p)
    # would over-exempt — e.g. /api/v1/auth/login-anything would slip through —
    # widening the unsafe-method surface, so keep matching precise.
    return any(path == p or path.startswith(p + "/") for p in exempt)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method.upper()
        path = request.url.path
        if method in _UNSAFE_METHODS and not is_exempt(path):
            cookie_token = request.cookies.get(settings.csrf_cookie_name)
            header_token = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
            if not csrf_tokens_match(cookie_token, header_token):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "CSRF_FAILED",
                            "message": "CSRF token missing or invalid.",
                            "details": [],
                            "request_id": request.headers.get("x-request-id", ""),
                        }
                    },
                )
        return await call_next(request)

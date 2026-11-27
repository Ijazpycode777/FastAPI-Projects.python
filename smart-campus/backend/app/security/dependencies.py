"""Authentication and authorization FastAPI dependencies.

These dependencies attach the authenticated user to the request state and
enforce role/resource-level access. Frontend route guards are a convenience
only; every protected backend endpoint must use one of these dependencies.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException, ForbiddenError, UnauthenticatedError
from app.database.session import get_db
from app.models.user import User
from app.models.session import Session as SessionModel
from app.security.sessions import set_session_cookie


async def get_current_user(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the session cookie.

    Raises UnauthenticatedError if there is no session, the session is
    revoked, the session has expired, or the underlying user is deactivated.
    """
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise UnauthenticatedError()

    result = await db.execute(
        select(SessionModel).where(
            SessionModel.token == token,
            SessionModel.revoked.is_(False),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise UnauthenticatedError("Session not found.")
    if session.is_expired():
        raise UnauthenticatedError("Session expired.")

    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthenticatedError("Account is unavailable.")

    # Enforce a forced password reset: an account flagged must_reset_password
    # may only call the password-change / profile / logout / csrf endpoints
    # until it changes its password. Prevents a reset/temporary credential from
    # being used to read or modify data.
    if getattr(user, "must_reset_password", False):
        path = request.url.path
        _reset_allowed = {
            f"{settings.api_v1_prefix}/auth/password",
            f"{settings.api_v1_prefix}/auth/me",
            f"{settings.api_v1_prefix}/auth/logout",
            f"{settings.api_v1_prefix}/auth/csrf",
        }
        if path not in _reset_allowed:
            raise AppException(
                "Password reset required before continuing.",
                status_code=403,
                code="PASSWORD_RESET_REQUIRED",
            )

    # Sliding session: keep active users logged in. Without this, expires_at is
    # fixed at login time and an active user is logged out on a rigid countdown
    # from login — the "page reloads to /login every minute" loop when
    # SESSION_MAX_AGE_SECONDS is set low. Extends expires_at (and refreshes the
    # cookie max_age so the browser doesn't drop the cookie first) only when
    # under 1/4 of the lifetime remains, so most requests stay read-only.
    await _slide_session(db, response, session, request)

    request.state.session_id = session.id
    request.state.user = user
    return user


async def _slide_session(
    db: AsyncSession, response: Response, session: SessionModel, request: Request
) -> None:
    """Extend the session expiry when it nears its lifetime boundary.

    A read-mostly pattern: skip the write entirely while more than 1/4 of the
    configured lifetime (``SESSION_MAX_AGE_SECONDS``) remains; only when the
    session is in its final quarter do we bump ``expires_at`` to now+lifetime,
    stamp ``last_seen_at``, commit, and re-issue the session cookie with a
    refreshed ``max_age`` so the browser keeps the cookie in lockstep with the
    server-side expiry.
    """
    now = datetime.now(timezone.utc)
    exp = session.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    lifetime = timedelta(seconds=settings.session_max_age_seconds)
    if exp - now >= lifetime / 4:
        return  # plenty of time left — no write needed
    new_exp = now + lifetime
    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session.id)
        .values(expires_at=new_exp, last_seen_at=now)
    )
    await db.commit()
    # Refresh the cookie max_age so the browser does not expire the cookie
    # before the (now extended) server-side session.
    set_session_cookie(response, session.token, settings.session_max_age_seconds, request)


CurrentUser = Depends(get_current_user)


def require_roles(*roles: str):
    """Dependency factory enforcing that the user has one of the given roles."""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("Your role does not permit this action.")
        return user

    return _checker


def require_admin():
    return require_roles("admin")


def require_teacher():
    return require_roles("teacher")


def require_student():
    return require_roles("student")


def require_staff():
    """Admin or teacher."""
    return require_roles("admin", "teacher")


def enforce_owner_or_admin(user: User, owner_id: str) -> None:
    """Resource-level authorization helper."""
    if user.role == "admin":
        return
    if str(user.id) != str(owner_id):
        raise ForbiddenError("You can only access your own resources.")

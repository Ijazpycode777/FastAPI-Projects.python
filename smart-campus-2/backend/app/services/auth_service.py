"""Authentication service: login, logout, session lifecycle, rate limiting."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException, ConflictError, UnauthenticatedError
from app.models.session import Session as SessionModel
from app.models.user import User
from app.repositories.audit import record_audit
from app.security.password import is_strong_password, verify_password
from app.security.sessions import (
    clear_csrf_cookie,
    clear_session_cookie,
    generate_csrf_token,
    generate_session_token,
    session_expires_at,
    set_csrf_cookie,
    set_session_cookie,
)


def _client_meta(request: Request) -> tuple[str, str]:
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")[:255]
    return ip, ua


async def _account_locked(user: User) -> bool:
    if user.locked_until:
        try:
            locked = datetime.fromisoformat(user.locked_until)
        except ValueError:
            return False
        if locked.tzinfo is None:
            locked = locked.replace(tzinfo=timezone.utc)
        return locked > datetime.now(timezone.utc)
    return False


async def login(
    db: AsyncSession, request: Request, response: Response, email: str, password: str
) -> tuple[User, str]:
    """Validate credentials, create a session, set cookies. Raises on failure."""
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    user = result.scalar_one_or_none()
    if user is None:
        # Constant-ish failure path: still do a hash verify to limit timing oracle.
        verify_password(password, "$argon2id$v=19$m=65536,t=3,p=2$AAA$AAA")
        raise UnauthenticatedError("Invalid email or password.")
    if await _account_locked(user):
        raise UnauthenticatedError("Account temporarily locked. Try again later.")
    if not user.is_active:
        raise UnauthenticatedError("Account is deactivated.")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.locked_until = (datetime.now(timezone.utc).isoformat())
            user.failed_login_attempts = 0
        await db.flush()
        raise UnauthenticatedError("Invalid email or password.")

    # Success — reset counters, rotate token (session fixation protection).
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc).isoformat()

    token = generate_session_token()
    expires = session_expires_at()
    ip, ua = _client_meta(request)
    session = SessionModel(
        token=token,
        user_id=user.id,
        expires_at=expires,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(session)

    # Revoke prior active sessions for this user (one active session per user).
    await db.execute(
        update(SessionModel)
        .where(SessionModel.user_id == user.id, SessionModel.id != session.id, SessionModel.revoked.is_(False))
        .values(revoked=True)
    )

    await db.flush()
    await record_audit(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()

    set_session_cookie(response, token, settings.session_max_age_seconds)
    csrf = generate_csrf_token()
    set_csrf_cookie(response, csrf)
    return user, csrf


async def logout(db: AsyncSession, request: Request, response: Response, user: User) -> None:
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        await db.execute(update(SessionModel).where(SessionModel.id == session_id).values(revoked=True))
    ip, ua = _client_meta(request)
    await record_audit(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="auth.logout",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    clear_session_cookie(response)
    clear_csrf_cookie(response)


async def issue_csrf(response: Response, user: Optional[User]) -> str:
    """Issue a fresh CSRF token cookie. Used after login & on demand."""
    token = generate_csrf_token()
    set_csrf_cookie(response, token)
    return token


async def change_password(db: AsyncSession, user: User, current: str, new: str) -> None:
    from app.security.password import hash_password
    if not verify_password(current, user.password_hash):
        raise AppException("Current password is incorrect.", status_code=400, code="BAD_REQUEST")
    ok, reason = is_strong_password(new)
    if not ok:
        raise AppException(reason or "Weak password.", status_code=422, code="VALIDATION_ERROR")
    user.password_hash = hash_password(new)
    user.must_reset_password = False
    await db.commit()


async def admin_reset_password(db: AsyncSession, target: User, request: Request) -> str:
    """Admin resets a user's password to a generated temporary value.

    The admin never sees the existing password. The temporary password is
    returned once and the user is flagged must_reset_password.
    """
    from app.security.password import hash_password
    from app.utils.helpers import generate_password
    temp = generate_password(12)
    target.password_hash = hash_password(temp)
    target.must_reset_password = True
    target.failed_login_attempts = 0
    target.locked_until = None
    ip, ua = _client_meta(request)
    await record_audit(
        db,
        actor_id=getattr(request.state, "user", None) and request.state.user.id,
        actor_role=getattr(request.state, "user", None) and request.state.user.role,
        action="auth.password_reset",
        resource_type="user",
        resource_id=target.id,
    )
    await db.commit()
    return temp

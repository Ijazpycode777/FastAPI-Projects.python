"""Authentication service: login, logout, session lifecycle, rate limiting."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException, ConflictError, UnauthenticatedError
from app.models.session import Session as SessionModel
from app.models.user import User
from app.repositories.audit import record_audit
from app.security.password import hash_password, is_strong_password, verify_password
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


# Real Argon2id hash of a fixed throwaway value, computed once and reused. When
# no user matches the supplied email we still run a full Argon2id verify against
# this hash so the no-user path takes roughly the same time as a bad-password
# path — limiting the timing oracle that distinct error messages would otherwise
# amplify. (Verifying a malformed hash returns immediately and gives NO parity,
# so we use a real, well-formed hash instead.)
_TIMING_PARITY_HASH: str | None = None


def _timing_parity_hash() -> str:
    global _TIMING_PARITY_HASH
    if _TIMING_PARITY_HASH is None:
        _TIMING_PARITY_HASH = hash_password("timing-parity-dummy-do-not-use")
    return _TIMING_PARITY_HASH


def _bad_credentials_message(*, wrong_password: bool) -> str:
    """Distinct, user-facing login failure messages.

    When ``login_distinct_error_messages`` is enabled the response tells the user
    which credential was wrong ("Incorrect email." vs "Incorrect password."). This
    is a deliberate UX choice that trades a user-enumeration oracle for clarity;
    set the flag False in hardened deployments to collapse both to the generic
    "Invalid email or password."
    """
    if not settings.login_distinct_error_messages:
        return "Invalid email or password."
    return "Incorrect password." if wrong_password else "Incorrect email."


async def login(
    db: AsyncSession, request: Request, response: Response, email: str, password: str
) -> tuple[User, str]:
    """Validate credentials, create a session, set cookies. Raises on failure."""
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    user = result.scalar_one_or_none()
    if user is None:
        # Timing-parity: run a full Argon2id verify against a real dummy hash so
        # this no-user path costs roughly the same as a bad-password verify.
        verify_password(password, _timing_parity_hash())
        raise UnauthenticatedError(_bad_credentials_message(wrong_password=False))
    if await _account_locked(user):
        raise UnauthenticatedError("Account temporarily locked. Try again later.")
    if not user.is_active:
        raise UnauthenticatedError("Account is deactivated.")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= settings.account_lockout_threshold:
            # Real FUTURE lockout: now + configured minutes, timezone-aware, so
            # _account_locked() (which compares against datetime.now(utc)) actually
            # holds the account until the lockout elapses.
            user.locked_until = (
                datetime.now(timezone.utc) + timedelta(minutes=settings.account_lockout_minutes)
            ).isoformat()
            user.failed_login_attempts = 0
        # COMMIT before raising so the counter/lockout survives the auth error.
        # The error propagates to the exception handler and the get_db dependency
        # rolls back its session on exit; without this commit the increment would
        # be lost and the lockout could never trigger.
        await db.commit()
        raise UnauthenticatedError(_bad_credentials_message(wrong_password=True))

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

    set_session_cookie(response, token, settings.session_max_age_seconds, request)
    csrf = generate_csrf_token()
    set_csrf_cookie(response, csrf, request)
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


async def issue_csrf(response: Response, request: Request, user: Optional[User]) -> str:
    """Issue a fresh CSRF token cookie. Used after login & on demand."""
    token = generate_csrf_token()
    set_csrf_cookie(response, token, request)
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

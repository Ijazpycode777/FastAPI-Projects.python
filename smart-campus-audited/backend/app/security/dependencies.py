"""Authentication and authorization FastAPI dependencies.

These dependencies attach the authenticated user to the request state and
enforce role/resource-level access. Frontend route guards are a convenience
only; every protected backend endpoint must use one of these dependencies.
"""
from __future__ import annotations

from typing import Sequence

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthenticatedError
from app.database.session import get_db
from app.models.user import User
from app.models.session import Session as SessionModel


async def get_current_user(
    request: Request,
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

    request.state.session_id = session.id
    request.state.user = user
    return user


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

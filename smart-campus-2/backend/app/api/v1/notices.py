"""Notices & notifications routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.communications import Notice, Notification
from app.models.user import User
from app.schemas.materials import NoticeIn, NoticeOut, NotificationOut
from app.security.dependencies import get_current_user, require_staff
from app.services import notice_service

router = APIRouter(tags=["notices"])


# ---------------- Notices ----------------
@router.get("/notices", response_model=list[NoticeOut])
async def list_notices(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [NoticeOut.model_validate(n) for n in await notice_service.list_for_user(db, user)]


@router.post("/notices", response_model=NoticeOut, dependencies=[Depends(require_staff())])
async def publish_notice(payload: NoticeIn, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    notice = await notice_service.publish(db, user, payload.model_dump())
    return NoticeOut.model_validate(notice)


@router.delete("/notices/{notice_id}", dependencies=[Depends(require_staff())])
async def delete_notice(notice_id: str, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise NotFoundError("Notice not found.")
    if user.role == "teacher" and str(notice.published_by) != str(user.id):
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("You can only delete your own notices.")
    await db.delete(notice)
    await db.commit()
    return {"message": "Notice deleted."}


# ---------------- Notifications ----------------
@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = (await db.execute(stmt.limit(50))).scalars().all()
    return [NotificationOut.model_validate(r) for r in rows]


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    n = await db.get(Notification, notification_id)
    if n is None or str(n.user_id) != str(user.id):
        raise NotFoundError("Notification not found.")
    n.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Marked as read."}


@router.post("/notifications/read-all")
async def mark_all_read(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    await db.execute(update(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    ).values(read_at=now))
    await db.commit()
    return {"message": "All notifications marked as read."}

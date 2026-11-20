"""Study materials & notice/notification schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class StudyMaterialOut(ORMBase):
    id: str
    title: str
    description: str | None = None
    subject_id: str
    class_id: str
    section_id: str | None = None
    uploaded_by: str | None = None
    created_at: datetime
    file_name: str
    file_size: int
    content_type: str
    is_active: bool


class StudyMaterialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = None
    subject_id: str
    class_id: str
    section_id: str | None = None


# ---------------- Notices ----------------
class NoticeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    target_audience: str = Field(default="all", pattern="^(all|admins|teachers|students|program|class|section)$")
    program_id: str | None = None
    class_id: str | None = None
    section_id: str | None = None
    expires_at: datetime | None = None
    is_pinned: bool = False


class NoticeOut(ORMBase):
    id: str
    title: str
    content: str
    published_by: str | None = None
    published_at: datetime
    target_audience: str
    program_id: str | None = None
    class_id: str | None = None
    section_id: str | None = None
    expires_at: datetime | None = None
    is_pinned: bool


# ---------------- Notifications ----------------
class NotificationOut(ORMBase):
    id: str
    type: str
    title: str
    body: str | None = None
    related_resource_type: str | None = None
    related_resource_id: str | None = None
    read_at: datetime | None = None
    created_at: datetime

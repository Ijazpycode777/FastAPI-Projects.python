"""Study materials: secure upload, authorized download, metadata persistence."""
from __future__ import annotations

from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.materials import StudyMaterial
from app.models.people import Student
from app.repositories.audit import record_audit
from app.services.academic_service import teacher_authorized_for
from app.services.file_validation import FileValidationError, validate_upload
from app.services.storage import get_storage, make_storage_key


async def upload(
    db: AsyncSession, actor, *, title: str, description: str | None,
    subject_id: str, class_id: str, section_id: str | None, file: UploadFile,
) -> StudyMaterial:
    if actor.role == "teacher":
        auth = await teacher_authorized_for(
            db, str(actor.teacher_profile.id), subject_id, class_id, section_id,
        )
        if not auth:
            raise ForbiddenError("You can only upload materials for subjects/classes assigned to you.")

    content = await file.read()
    detected = file.content_type or "application/octet-stream"
    try:
        ext = validate_upload(file.filename or "upload", len(content), detected)
    except FileValidationError as exc:
        raise ForbiddenError(str(exc))

    storage = get_storage()
    key = make_storage_key(file.filename or f"upload.{ext}")
    import io
    storage.save(key, io.BytesIO(content), detected)

    material = StudyMaterial(
        title=title, description=description,
        subject_id=subject_id, class_id=class_id, section_id=section_id,
        uploaded_by=actor.id, storage_backend=settings_storage_backend(),
        storage_key=key, file_name=file.filename or f"upload.{ext}",
        file_size=len(content), content_type=detected, is_active=True,
    )
    db.add(material)
    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="material.upload", resource_type="study_material", resource_id=material.id)
    await db.commit()
    await db.refresh(material)
    return material


def settings_storage_backend() -> str:
    from app.core.config import settings
    return settings.storage_backend


async def list_for_student(db: AsyncSession, student: Student) -> list[StudyMaterial]:
    """Materials the student is authorized to see: their class (+ section if set)."""
    if student.current_class_id is None:
        return []
    stmt = select(StudyMaterial).where(
        StudyMaterial.class_id == student.current_class_id,
        StudyMaterial.is_active.is_(True),
    )
    if student.current_section_id:
        stmt = stmt.where(
            (StudyMaterial.section_id == student.current_section_id) | (StudyMaterial.section_id.is_(None))
        )
    return list((await db.execute(stmt.order_by(StudyMaterial.created_at.desc()))).scalars().all())


async def download(db: AsyncSession, user, material_id: str) -> tuple[StudyMaterial, BinaryIO]:
    material = await db.get(StudyMaterial, material_id)
    if material is None or not material.is_active:
        raise NotFoundError("Study material not found.")
    if user.role == "student":
        student = user.student_profile
        if str(material.class_id) != str(student.current_class_id):
            raise ForbiddenError("You are not authorized to download this material.")
        if material.section_id and str(material.section_id) != str(student.current_section_id):
            raise ForbiddenError("You are not authorized to download this material.")
    elif user.role == "teacher":
        auth = await teacher_authorized_for(
            db, str(user.teacher_profile.id), str(material.subject_id),
            str(material.class_id), str(material.section_id) if material.section_id else None,
        )
        if not auth:
            raise ForbiddenError("You are not authorized to download this material.")
    storage = get_storage()
    return material, storage.open(material.storage_key)

"""Study materials: secure upload, authorized download, metadata persistence."""
from __future__ import annotations

import io
import os
import tempfile
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.materials import StudyMaterial
from app.models.people import Student
from app.repositories.audit import record_audit
from app.services.academic_service import teacher_authorized_for
from app.services.file_validation import FileValidationError, validate_upload
from app.services.storage import get_storage, make_storage_key

# Chunk size for bounded upload reading. Small enough that a single read never
# holds a large buffer, large enough to keep the loop overhead negligible.
_READ_CHUNK = 64 * 1024  # 64 KiB


async def _read_bounded(file: UploadFile, max_bytes: int) -> tuple[str, int]:
    """Stream the upload into a fresh temp file, capped at ``max_bytes``.

    Reads in fixed chunks so an attacker cannot exhaust memory with an
    arbitrarily large upload: as soon as the accumulated size exceeds
    ``max_bytes`` we stop reading and raise ``FileValidationError``. The temp
    file is removed on any failure (including the oversize rejection) so no
    partial upload is left behind. On success the caller owns the temp file and
    is responsible for deleting it.

    Returns ``(temp_path, actual_size)``.
    """
    fd, path = tempfile.mkstemp(prefix="sc_upload_", suffix=".bin")
    os.close(fd)
    total = 0
    try:
        with open(path, "wb") as fh:
            while True:
                chunk = await file.read(_READ_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    # Stop reading immediately — do not store the whole upload.
                    raise FileValidationError(
                        f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit."
                    )
                fh.write(chunk)
    except BaseException:
        # Cleanup the partial temp file on ANY failure (oversize, network
        # error, …) so nothing is left on disk. The caller never sees the path.
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path, total


async def upload(
    db: AsyncSession, actor, *, title: str, description: str | None,
    subject_id: str, class_id: str, section_id: str | None, file: UploadFile,
) -> StudyMaterial:
    # Authorize BEFORE reading any bytes so a forbidden request never pays the
    # cost of (or stores) the upload.
    if actor.role == "teacher":
        auth = await teacher_authorized_for(
            db, str(actor.teacher_profile.id), subject_id, class_id, section_id,
        )
        if not auth:
            raise ForbiddenError("You can only upload materials for subjects/classes assigned to you.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    tmp_path: str | None = None
    storage_key: str | None = None
    try:
        # 1. Bounded read to a temp file — rejects oversize uploads while
        #    reading, never holding more than a chunk in memory.
        tmp_path, size = await _read_bounded(file, max_bytes)

        # 2. Verify the actual content BEFORE persisting anything. The temp
        #    file is the source of truth; the browser-supplied MIME is ignored.
        with open(tmp_path, "rb") as fh:
            data = fh.read()
        ext, mime = validate_upload(file.filename or "upload", data)

        # 3. Persist the validated bytes to storage.
        storage = get_storage()
        storage_key = make_storage_key(file.filename or f"upload.{ext}")
        storage.save(storage_key, io.BytesIO(data), mime)

        # 4. Only after the file is safely stored do we create the DB record.
        material = StudyMaterial(
            title=title, description=description,
            subject_id=subject_id, class_id=class_id, section_id=section_id,
            uploaded_by=actor.id, storage_backend=settings_storage_backend(),
            storage_key=storage_key, file_name=file.filename or f"upload.{ext}",
            file_size=size, content_type=mime, is_active=True,
        )
        db.add(material)
        await db.flush()
        await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                           action="material.upload", resource_type="study_material", resource_id=material.id)
        await db.commit()
        await db.refresh(material)
        return material
    except FileValidationError as exc:
        # Invalid file → 422, never 500. No storage save / DB record was made
        # (validation happens before both). Roll back any pending state.
        await db.rollback()
        raise ValidationError(str(exc))
    except Exception:
        # Any other failure (e.g. storage write error, DB commit failure):
        # roll back the DB and remove any stored file so no partial upload or
        # orphaned DB row survives.
        await db.rollback()
        if storage_key is not None:
            try:
                get_storage().delete(storage_key)
            except Exception:
                pass
        raise
    finally:
        # The temp file is always cleaned up — success or failure.
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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

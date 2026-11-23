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
from app.models.academic import ClassLevel
from app.models.materials import StudyMaterial
from app.models.people import Student
from app.repositories.audit import record_audit
from app.services.academic_service import resolve_or_create_subject, teacher_assigned_to_class
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
    subject: str, class_id: str, section_id: str | None, file: UploadFile,
) -> StudyMaterial:
    # Resolve the class → program so the typed subject name can be matched
    # (or created) within the right program. A missing class is a 404, not a
    # 500 from a later FK violation on the material row.
    class_level = await db.get(ClassLevel, class_id)
    if class_level is None:
        raise NotFoundError("Selected class does not exist.")
    program_id = str(class_level.program_id)

    # Authorize BEFORE reading any bytes so a forbidden request never pays the
    # cost of (or stores) the upload. The subject is now a free-text label, so
    # the check is class-level: a teacher may upload for any class they are
    # assigned to (any subject/section), not only a specific subject assignment.
    if actor.role == "teacher":
        teacher_id = str(actor.teacher_profile.id)
        if not await teacher_assigned_to_class(db, teacher_id, class_id):
            raise ForbiddenError("You can only upload materials for classes assigned to you.")

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

        # 3. Resolve the typed subject name to a Subject row (creating it if it
        #    is new to this program) AFTER content validation, so a rejected
        #    upload never leaves an orphan subject. The flush shares this
        #    transaction and rolls back with it on any later failure.
        subject_obj = await resolve_or_create_subject(db, program_id, subject)

        # 4. Persist the validated bytes to storage.
        storage = get_storage()
        storage_key = make_storage_key(file.filename or f"upload.{ext}")
        storage.save(storage_key, io.BytesIO(data), mime)

        # 5. Only after the file is safely stored do we create the DB record.
        material = StudyMaterial(
            title=title, description=description,
            subject_id=str(subject_obj.id), class_id=class_id, section_id=section_id,
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
        # Class-level authz (consistent with upload): a teacher assigned to the
        # class may download its materials, and the uploader always may. This
        # matters now that the subject is a free-text label that may not appear
        # in the teacher's own assignment list.
        teacher_id = str(user.teacher_profile.id)
        owns = str(getattr(material, "uploaded_by", "")) == str(user.id)
        if not (owns or await teacher_assigned_to_class(db, teacher_id, str(material.class_id))):
            raise ForbiddenError("You are not authorized to download this material.")
    storage = get_storage()
    return material, storage.open(material.storage_key)

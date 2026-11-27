"""Study materials: secure upload, authorized download, metadata persistence.

File bytes are stored in the database (``StudyMaterial.file_data``) so a
material is retained exactly as uploaded until a teacher or admin deletes it
(the bytes are nulled on delete; the audit row stays). The ``file_data`` column
is deferred at the ORM level, so list queries never load every file's bytes;
the download/preview path explicitly ``undefer``s it for the one row it needs.
Rows created before the column existed (``file_data`` NULL) keep their bytes in
local/S3 storage and the download falls back to the storage backend for them.
"""
from __future__ import annotations

import os
import tempfile
from io import BytesIO
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.academic import ClassLevel
from app.models.materials import StudyMaterial
from app.models.people import Student
from app.repositories.audit import record_audit
from app.services.academic_service import teacher_assigned_to_class
from app.services.file_validation import FileValidationError, validate_upload_path
from app.services.storage import get_storage

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
    class_id: str, file: UploadFile,
) -> StudyMaterial:
    # Validate the class up front so a bad class_id is a 404, not a 500 from a
    # later FK violation on the material row.
    class_level = await db.get(ClassLevel, class_id)
    if class_level is None:
        raise NotFoundError("Selected class does not exist.")

    # Authorize BEFORE reading any bytes so a forbidden request never pays the
    # cost of (or stores) the upload. A material is scoped to a single class, so
    # the check is class-level: a teacher may upload for any class they are
    # assigned to (any subject/section).
    if actor.role == "teacher":
        teacher_id = str(actor.teacher_profile.id)
        if not await teacher_assigned_to_class(db, teacher_id, class_id):
            raise ForbiddenError("You can only upload materials for classes assigned to you.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    tmp_path: str | None = None
    try:
        # 1. Bounded read to a temp file — rejects oversize uploads while
        #    reading, never holding more than a chunk in memory.
        tmp_path, size = await _read_bounded(file, max_bytes)

        # 2. Verify the actual content BEFORE persisting anything, streaming
        #    from the temp file — the whole upload is never held in memory. The
        #    browser-supplied MIME is ignored; the type comes from the verified
        #    content (and includes zip-bomb guards for DOCX/PPTX).
        ext, mime = validate_upload_path(file.filename or "upload", tmp_path)

        # 3. Read the verified bytes. The temp file is already capped at
        #    max_bytes, so this read is bounded by the upload limit. The bytes
        #    are persisted in the database (file_data) so the material is
        #    durable across storage-volume recycling and is removed only when a
        #    teacher/admin deletes the material.
        with open(tmp_path, "rb") as fh:
            file_data = fh.read()

        # 4. Create the DB record with the bytes inline. storage_key/backend are
        #    retained for backward compatibility with legacy rows (whose bytes
        #    live in local/S3 storage and whose file_data is NULL); for new
        #    uploads the bytes are in file_data and storage_key is a placeholder.
        material = StudyMaterial(
            title=title, description=description,
            class_id=class_id,
            uploaded_by=actor.id, storage_backend="db",
            storage_key="db", file_name=file.filename or f"upload.{ext}",
            file_size=size, content_type=mime, is_active=True,
            file_data=file_data,
        )
        db.add(material)
        await db.flush()
        await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                           action="material.upload", resource_type="study_material", resource_id=material.id)
        await db.commit()
        await db.refresh(material)
        return material
    except FileValidationError as exc:
        # Invalid file → 422, never 500. No DB record was made (validation
        # happens before the insert). Roll back any pending state.
        await db.rollback()
        raise ValidationError(str(exc))
    except Exception:
        # Any other failure (e.g. DB commit failure): roll back the DB so no
        # orphaned row survives. There is no storage file to clean up (bytes
        # are in file_data, rolled back with the row).
        await db.rollback()
        raise
    finally:
        # The temp file is always cleaned up — success or failure.
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


async def list_for_student(db: AsyncSession, student: Student) -> list[StudyMaterial]:
    """Materials the student is authorized to see: their exact class only.

    ``current_class_id`` points at a specific ClassLevel row, which already
    encodes (program, part) — e.g. "ICS Part 1" is a different row from
    "Medical Part 1". Filtering by ``class_id`` therefore guarantees that a PDF
    uploaded for ICS Part 1 never surfaces for Medical students or for "Part 1"
    of any other program.
    """
    if student.current_class_id is None:
        return []
    stmt = select(StudyMaterial).where(
        StudyMaterial.class_id == student.current_class_id,
        StudyMaterial.is_active.is_(True),
    )
    return list((await db.execute(stmt.order_by(StudyMaterial.created_at.desc()))).scalars().all())


async def download(db: AsyncSession, user, material_id: str) -> tuple[StudyMaterial, BinaryIO]:
    # undefer(file_data) so the one row's bytes are loaded in this query; the
    # list endpoint never loads file_data (deferred at the model level).
    stmt = select(StudyMaterial).options(undefer(StudyMaterial.file_data)).where(
        StudyMaterial.id == material_id,
    )
    material = (await db.execute(stmt)).scalar_one_or_none()
    if material is None or not material.is_active:
        raise NotFoundError("Study material not found.")
    if user.role == "student":
        student = user.student_profile
        if str(material.class_id) != str(student.current_class_id):
            raise ForbiddenError("You are not authorized to download this material.")
    elif user.role == "teacher":
        # Class-level authz (consistent with upload): a teacher assigned to the
        # class may download its materials, and the uploader always may.
        teacher_id = str(user.teacher_profile.id)
        owns = str(getattr(material, "uploaded_by", "")) == str(user.id)
        if not (owns or await teacher_assigned_to_class(db, teacher_id, str(material.class_id))):
            raise ForbiddenError("You are not authorized to download this material.")
    # New rows store bytes in file_data (DB). Legacy rows (file_data NULL) keep
    # their bytes in local/S3 storage — fall back to the storage backend.
    if material.file_data is not None:
        return material, BytesIO(material.file_data)
    storage = get_storage()
    return material, storage.open(material.storage_key)

"""Study materials routes: upload (staff) + list/download (authorized)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.materials import StudyMaterial
from app.models.user import User
from app.schemas.materials import StudyMaterialOut
from app.security.dependencies import get_current_user, require_staff, require_student
from app.services import material_service

router = APIRouter(prefix="/materials", tags=["materials"])


@router.post("", response_model=StudyMaterialOut, dependencies=[Depends(require_staff())])
async def upload(
    title: str = Form(...),
    description: str | None = Form(None),
    subject_id: str = Form(...),
    class_id: str = Form(...),
    section_id: str | None = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(require_staff()),
    db: AsyncSession = Depends(get_db),
):
    material = await material_service.upload(
        db, user, title=title, description=description,
        subject_id=subject_id, class_id=class_id, section_id=section_id, file=file,
    )
    return StudyMaterialOut.model_validate(material)


@router.get("", response_model=list[StudyMaterialOut])
async def list_materials(
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role == "student":
        rows = await material_service.list_for_student(db, user.student_profile)
    else:
        stmt = select(StudyMaterial).where(StudyMaterial.is_active.is_(True)).order_by(StudyMaterial.created_at.desc())
        if subject_id:
            stmt = stmt.where(StudyMaterial.subject_id == subject_id)
        if class_id:
            stmt = stmt.where(StudyMaterial.class_id == class_id)
        rows = (await db.execute(stmt.limit(100))).scalars().all()
    return [StudyMaterialOut.model_validate(r) for r in rows]


@router.get("/{material_id}/download")
async def download(material_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    material, stream = await material_service.download(db, user, material_id)
    # Sanitize the filename for the Content-Disposition header: strip CR/LF and
    # double quotes so a maliciously-named upload cannot inject header fields.
    raw_name = material.file_name or "download"
    safe_name = "".join(ch for ch in raw_name if ch not in "\r\n\"").strip() or "download"
    return StreamingResponse(stream, media_type=material.content_type,
                             headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})


@router.delete("/{material_id}", dependencies=[Depends(require_staff())])
async def delete(material_id: str, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    material = await db.get(StudyMaterial, material_id)
    if material is None:
        raise NotFoundError("Study material not found.")
    material.is_active = False
    await db.commit()
    return {"message": "Material removed."}

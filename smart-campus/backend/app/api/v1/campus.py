"""Campus shift + roll-number scheme routes (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.campus import CampusShift, RollNumberScheme
from app.models.user import User
from app.schemas.campus import (
    CampusShiftIn,
    CampusShiftOut,
    CampusShiftUpdateIn,
    RollNumberSchemeIn,
    RollNumberSchemeOut,
    RollNumberSchemeUpdateIn,
)
from app.security.dependencies import require_admin
from app.services import campus_service

router = APIRouter(prefix="/campus", tags=["campus"])


# ---------------- Shifts ----------------
@router.get("/shifts", response_model=list[CampusShiftOut], dependencies=[Depends(require_admin())])
async def list_shifts(admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return [CampusShiftOut.model_validate(s) for s in await campus_service.list_shifts(db)]


@router.post("/shifts", response_model=CampusShiftOut, dependencies=[Depends(require_admin())])
async def create_shift(payload: CampusShiftIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return CampusShiftOut.model_validate(await campus_service.create_shift(db, admin, payload.model_dump()))


@router.get("/shifts/{shift_id}", response_model=CampusShiftOut, dependencies=[Depends(require_admin())])
async def get_shift(shift_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    s = await db.get(CampusShift, shift_id)
    if s is None:
        raise NotFoundError("Campus shift not found.")
    return CampusShiftOut.model_validate(s)


@router.patch("/shifts/{shift_id}", response_model=CampusShiftOut, dependencies=[Depends(require_admin())])
async def update_shift(
    shift_id: str, payload: CampusShiftUpdateIn,
    admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db),
):
    s = await db.get(CampusShift, shift_id)
    if s is None:
        raise NotFoundError("Campus shift not found.")
    return CampusShiftOut.model_validate(await campus_service.update_shift(db, admin, s, payload.model_dump(exclude_unset=True)))


# ---------------- Roll-number schemes ----------------
@router.get("/roll-schemes", response_model=list[RollNumberSchemeOut], dependencies=[Depends(require_admin())])
async def list_schemes(
    campus_shift_id: str | None = Query(None),
    class_id: str | None = Query(None),
    admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db),
):
    return [RollNumberSchemeOut.model_validate(r) for r in await campus_service.list_schemes(db, campus_shift_id, class_id)]


@router.post("/roll-schemes", response_model=RollNumberSchemeOut, dependencies=[Depends(require_admin())])
async def create_scheme(payload: RollNumberSchemeIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return RollNumberSchemeOut.model_validate(await campus_service.create_scheme(db, admin, payload.model_dump()))


@router.patch("/roll-schemes/{scheme_id}", response_model=RollNumberSchemeOut, dependencies=[Depends(require_admin())])
async def update_scheme(
    scheme_id: str, payload: RollNumberSchemeUpdateIn,
    admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db),
):
    r = await db.get(RollNumberScheme, scheme_id)
    if r is None:
        raise NotFoundError("Roll-number scheme not found.")
    return RollNumberSchemeOut.model_validate(await campus_service.update_scheme(db, admin, r, payload.model_dump(exclude_unset=True)))


@router.delete("/roll-schemes/{scheme_id}", status_code=204, dependencies=[Depends(require_admin())])
async def delete_scheme(scheme_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    r = await db.get(RollNumberScheme, scheme_id)
    if r is None:
        raise NotFoundError("Roll-number scheme not found.")
    await campus_service.delete_scheme(db, admin, r)

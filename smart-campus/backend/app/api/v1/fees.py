"""Fee management routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.fees import FeeInvoice, FeeStructure, Payment
from app.models.user import User
from app.schemas.fees import (
    FeeInvoiceOut,
    FeeStructureIn,
    FeeStructureOut,
    InvoiceDetailOut,
    InvoiceGenerateIn,
    PaymentIn,
    PaymentOut,
)
from app.security.dependencies import get_current_user, require_admin, require_student
from app.services import fee_service

router = APIRouter(prefix="/fees", tags=["fees"])


@router.get("/structures", response_model=list[FeeStructureOut])
async def list_structures(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(FeeStructure).where(FeeStructure.is_active.is_(True)).order_by(FeeStructure.name))
    return [FeeStructureOut.model_validate(r) for r in rows.scalars().all()]


@router.post("/structures", response_model=FeeStructureOut, dependencies=[Depends(require_admin())])
async def create_structure(payload: FeeStructureIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return FeeStructureOut.model_validate(await fee_service.create_structure(db, admin, **payload.model_dump()))


@router.post("/invoices", response_model=FeeInvoiceOut, dependencies=[Depends(require_admin())])
async def generate_invoice(payload: InvoiceGenerateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return FeeInvoiceOut.model_validate(await fee_service.generate_invoice(db, admin, payload.model_dump()))


@router.get("/invoices", response_model=list[FeeInvoiceOut])
async def list_invoices(student_id: str | None = Query(None), status: str | None = Query(None),
                        admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    stmt = select(FeeInvoice).order_by(FeeInvoice.issued_date.desc())
    if student_id:
        stmt = stmt.where(FeeInvoice.student_id == student_id)
    if status:
        stmt = stmt.where(FeeInvoice.status == status)
    return [FeeInvoiceOut.model_validate(r) for r in (await db.execute(stmt.limit(200))).scalars().all()]


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailOut)
async def invoice_detail(invoice_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    invoice = await db.get(FeeInvoice, invoice_id)
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    if user.role == "student" and str(invoice.student_id) != str(user.student_profile.id):
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("Not your invoice.")
    detail = await fee_service.invoice_detail(db, invoice)
    out = InvoiceDetailOut(**FeeInvoiceOut.model_validate(invoice).model_dump(),
                           paid_amount=detail["paid_amount"], outstanding=detail["outstanding"],
                           payments=[PaymentOut.model_validate(p) for p in detail["payments"]])
    return out


@router.post("/payments", response_model=PaymentOut, dependencies=[Depends(require_admin())])
async def record_payment(payload: PaymentIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return PaymentOut.model_validate(await fee_service.record_payment(db, admin, payload.model_dump()))


@router.get("/statement/me", tags=["student-self"])
async def my_statement(user: User = Depends(require_student()), db: AsyncSession = Depends(get_db)):
    return await fee_service.student_statement(db, str(user.student_profile.id))


@router.get("/statement/{student_id}")
async def statement(student_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "student" and str(user.student_profile.id) != str(student_id):
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("Not your statement.")
    return await fee_service.student_statement(db, student_id)

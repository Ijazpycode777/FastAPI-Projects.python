"""Fee service: structures, invoices, payments, outstanding balances.

Money is stored as Numeric(12,2) in the DB; we compute with floats via the
pure ``fees_calc`` helpers and round to 2 decimals everywhere.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.fees import FeeInvoice, FeeStructure, Payment
from app.models.people import Student
from app.repositories.audit import record_audit
from app.services.fees_calc import invoice_status, outstanding as out_bal, paid_amount


async def create_structure(db: AsyncSession, actor, **kw) -> FeeStructure:
    obj = FeeStructure(**kw)
    db.add(obj)
    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="fee_structure.create", resource_type="fee_structure", resource_id=obj.id)
    await db.commit()
    await db.refresh(obj)
    return obj


async def _next_invoice_number(db: AsyncSession, session_id: str) -> str:
    count = (await db.execute(select(func.count()).select_from(FeeInvoice).where(
        FeeInvoice.academic_session_id == session_id
    ))).scalar_one()
    year = date.today().year
    return f"INV-{year}-{count + 1:05d}"


async def generate_invoice(db: AsyncSession, actor, data: dict[str, Any]) -> FeeInvoice:
    structure = await db.get(FeeStructure, data["fee_structure_id"])
    if structure is None or not structure.is_active:
        raise NotFoundError("Fee structure not found or inactive.")
    student = await db.get(Student, data["student_id"])
    if student is None:
        raise NotFoundError("Student not found.")

    issued = data.get("issued_date") or date.today()
    due = issued + timedelta(days=structure.due_after_days)
    number = await _next_invoice_number(db, structure.academic_session_id)

    invoice = FeeInvoice(
        invoice_number=number,
        student_id=student.id,
        fee_structure_id=structure.id,
        academic_session_id=structure.academic_session_id,
        amount=float(structure.amount),
        issued_date=issued,
        due_date=due,
        status="unpaid",
        issued_by=actor.id,
        note=data.get("note"),
    )
    db.add(invoice)
    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="invoice.generate", resource_type="fee_invoice", resource_id=invoice.id,
                       after={"invoice_number": number, "amount": float(structure.amount)})
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def _next_receipt_number(db: AsyncSession) -> str:
    count = (await db.execute(select(func.count()).select_from(Payment))).scalar_one()
    return f"RCP-{count + 1:06d}"


async def record_payment(db: AsyncSession, actor, data: dict[str, Any]) -> Payment:
    invoice = await db.get(FeeInvoice, data["invoice_id"])
    if invoice is None:
        raise NotFoundError("Invoice not found.")

    payments = await db.execute(select(Payment).where(Payment.invoice_id == invoice.id))
    paid = sum(float(p.amount) for p in payments.scalars().all())
    if paid + data["amount"] > float(invoice.amount) + 0.01:
        raise ValidationError("Payment exceeds outstanding balance.")

    receipt = await _next_receipt_number(db)
    payment = Payment(
        invoice_id=invoice.id, student_id=invoice.student_id,
        amount=float(data["amount"]), paid_at=data["paid_at"],
        method=data["method"], reference=data.get("reference"),
        recorded_by=actor.id, receipt_number=receipt,
    )
    db.add(payment)
    await db.flush()

    new_paid = paid + float(data["amount"])
    due_passed = invoice.due_date < data["paid_at"]
    invoice.status = invoice_status(float(invoice.amount), new_paid, due_passed)

    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="payment.record", resource_type="payment", resource_id=payment.id,
                       after={"amount": float(data["amount"]), "receipt": receipt})
    await db.commit()
    await db.refresh(payment)
    return payment


async def invoice_detail(db: AsyncSession, invoice: FeeInvoice) -> dict[str, Any]:
    payments = await db.execute(select(Payment).where(Payment.invoice_id == invoice.id).order_by(Payment.paid_at))
    rows = list(payments.scalars().all())
    paid = sum(float(p.amount) for p in rows)
    return {
        "paid_amount": round(paid, 2),
        "outstanding": round(max(float(invoice.amount) - paid, 0.0), 2),
        "payments": rows,
    }


async def student_statement(db: AsyncSession, student_id: str) -> dict[str, Any]:
    invoices = await db.execute(
        select(FeeInvoice).where(FeeInvoice.student_id == student_id).order_by(FeeInvoice.issued_date)
    )
    rows = list(invoices.scalars().all())
    total_invoiced = sum(float(i.amount) for i in rows)
    total_paid = 0.0
    out = 0.0
    line_items = []
    for inv in rows:
        d = await invoice_detail(db, inv)
        total_paid += d["paid_amount"]
        out += d["outstanding"]
        line_items.append({"invoice": inv, **d})
    return {
        "student_id": student_id,
        "total_invoiced": round(total_invoiced, 2),
        "total_paid": round(total_paid, 2),
        "total_outstanding": round(out, 2),
        "items": line_items,
    }

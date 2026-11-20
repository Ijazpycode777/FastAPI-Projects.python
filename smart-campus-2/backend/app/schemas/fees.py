"""Fee management schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class FeeStructureIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    program_id: str | None = None
    class_id: str | None = None
    academic_session_id: str
    amount: float = Field(ge=0, le=10_000_000)
    frequency: str = Field(default="one_time", pattern="^(one_time|monthly|quarterly|annual)$")
    due_after_days: int = Field(default=30, ge=0, le=365)
    is_active: bool = True


class FeeStructureOut(ORMBase):
    id: str
    name: str
    program_id: str | None = None
    class_id: str | None = None
    academic_session_id: str
    amount: float
    frequency: str
    due_after_days: int
    is_active: bool


class InvoiceGenerateIn(BaseModel):
    student_id: str
    fee_structure_id: str
    issued_date: date | None = None
    note: str | None = None


class FeeInvoiceOut(ORMBase):
    id: str
    invoice_number: str
    student_id: str
    fee_structure_id: str
    academic_session_id: str
    amount: float
    issued_date: date
    due_date: date
    status: str
    issued_by: str | None = None
    note: str | None = None


class InvoiceDetailOut(FeeInvoiceOut):
    paid_amount: float
    outstanding: float
    payments: list["PaymentOut"] = []


class PaymentIn(BaseModel):
    invoice_id: str
    amount: float = Field(gt=0, le=10_000_000)
    paid_at: date
    method: str = Field(pattern="^(cash|cheque|bank_transfer|card|online)$")
    reference: str | None = None


class PaymentOut(ORMBase):
    id: str
    invoice_id: str
    student_id: str
    amount: float
    paid_at: date
    method: str
    reference: str | None = None
    receipt_number: str

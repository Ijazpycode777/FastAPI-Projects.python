"""Fee management: structures, invoices, payments.

Money is stored as Numeric(12, 2) — never floating point. Outstanding balance
is always derived from authoritative invoice + payment records.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK
from app.utils.helpers import sql_in

INVOICE_STATUSES = ("unpaid", "partial", "paid", "overdue", "void")
PAYMENT_METHODS = ("cash", "cheque", "bank_transfer", "card", "online")


class FeeStructure(UUIDPK, TimestampMixin, Base):
    """A configurable fee category + amount scoped to program/class/session."""
    __tablename__ = "fee_structures"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="fee_amount_check"),
        CheckConstraint("frequency IN ('one_time','monthly','quarterly','annual')", name="fee_frequency_check"),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    program_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=True
    )
    class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="RESTRICT"), nullable=True
    )
    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    frequency: Mapped[str] = mapped_column(String(12), nullable=False, default="one_time")
    due_after_days: Mapped[int] = mapped_column(nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class FeeInvoice(UUIDPK, TimestampMixin, Base):
    __tablename__ = "fee_invoices"
    __table_args__ = (
        CheckConstraint(
            f"status IN {sql_in(INVOICE_STATUSES)}",
            name="invoice_status_check",
        ),
        CheckConstraint("amount >= 0", name="invoice_amount_check"),
        Index("ix_invoice_student_status", "student_id", "status"),
        Index("ix_invoice_session", "academic_session_id"),
    )

    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    fee_structure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fee_structures.id", ondelete="RESTRICT"), nullable=False
    )
    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="unpaid")
    issued_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    student = relationship("Student")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


class Payment(UUIDPK, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            f"method IN {sql_in(PAYMENT_METHODS)}",
            name="payment_method_check",
        ),
        CheckConstraint("amount > 0", name="payment_amount_check"),
        Index("ix_payment_invoice", "invoice_id"),
        Index("ix_payment_student", "student_id"),
    )

    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fee_invoices.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recorded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    receipt_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    invoice = relationship("FeeInvoice", back_populates="payments")

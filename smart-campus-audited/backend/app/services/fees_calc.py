"""Fee calculations (pure logic). Money is float here only for computation;
in the DB it is stored as Numeric(12, 2). We use round(…, 2) everywhere.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InvoiceView:
    invoice_id: str
    amount: float
    payments: list[float]   # list of payment amounts


def paid_amount(invoice: InvoiceView) -> float:
    return round(sum(invoice.payments), 2)


def outstanding(invoice: InvoiceView) -> float:
    return round(max(invoice.amount - paid_amount(invoice), 0.0), 2)


def invoice_status(amount: float, paid: float, due_passed: bool) -> str:
    """Derive invoice status from authoritative records.

    paid >= amount            -> 'paid'
    0 < paid < amount         -> 'partial' (or 'overdue' if past due)
    paid == 0 and past due    -> 'overdue'
    paid == 0 and not past    -> 'unpaid'
    """
    if paid >= amount and amount > 0:
        return "paid"
    if paid <= 0:
        return "overdue" if due_passed else "unpaid"
    return "overdue" if due_passed else "partial"


def total_outstanding(invoices: list[InvoiceView]) -> float:
    return round(sum(outstanding(i) for i in invoices), 2)


def total_paid(invoices: list[InvoiceView]) -> float:
    return round(sum(paid_amount(i) for i in invoices), 2)


def next_invoice_number(prefix: str, sequence: int) -> str:
    """INV-2025-0001 style."""
    return f"{prefix}-{sequence:04d}"


def next_receipt_number(sequence: int) -> str:
    return f"RCP-{sequence:06d}"

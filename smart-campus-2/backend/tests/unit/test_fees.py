"""Unit tests: fee calculations."""
from app.services.fees_calc import (
    InvoiceView,
    invoice_status,
    outstanding,
    paid_amount,
    total_outstanding,
    total_paid,
    next_invoice_number,
    next_receipt_number,
)


def test_outstanding():
    inv = InvoiceView("i1", 5000, [2000, 1000])
    assert paid_amount(inv) == 3000
    assert outstanding(inv) == 2000


def test_outstanding_cannot_go_negative():
    inv = InvoiceView("i1", 1000, [1500])
    assert outstanding(inv) == 0.0


def test_status_paid():
    assert invoice_status(5000, 5000, due_passed=True) == "paid"
    assert invoice_status(5000, 6000, due_passed=False) == "paid"


def test_status_partial():
    assert invoice_status(5000, 2000, due_passed=False) == "partial"


def test_status_overdue():
    assert invoice_status(5000, 0, due_passed=True) == "overdue"
    assert invoice_status(5000, 2000, due_passed=True) == "overdue"


def test_status_unpaid():
    assert invoice_status(5000, 0, due_passed=False) == "unpaid"


def test_totals():
    invoices = [InvoiceView("i1", 5000, [2000]), InvoiceView("i2", 1000, [])]
    assert total_paid(invoices) == 2000
    assert total_outstanding(invoices) == 4000


def test_number_generators():
    assert next_invoice_number("INV", 7) == "INV-0007"
    assert next_receipt_number(42) == "RCP-000042"

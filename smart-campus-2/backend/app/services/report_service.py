"""Reports & exports: Excel (openpyxl) and PDF (reportlab) generators.

Export operations always use authorized DB records passed in by the route
layer — these functions never query the database themselves.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any


def _xlsx(rows: list[dict[str, Any]], headers: list[str]) -> BytesIO:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _pdf(title: str, lines: list[tuple[str, str]]) -> BytesIO:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=title)
    styles = getSampleStyleSheet()
    flow = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    for label, value in lines:
        flow.append(Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]))
    doc.build(flow)
    buf.seek(0)
    return buf


def students_xlsx(students: list[dict[str, Any]]) -> BytesIO:
    headers = ["admission_number", "full_name", "email", "class", "section", "status"]
    return _xlsx(students, headers)


def attendance_xlsx(rows: list[dict[str, Any]]) -> BytesIO:
    headers = ["student_id", "present", "absent", "late", "excused", "percentage"]
    return _xlsx(rows, headers)


def fee_statement_pdf(student: dict[str, Any], statement: dict[str, Any]) -> BytesIO:
    lines = [
        ("Student", student.get("full_name", "")),
        ("Admission No.", student.get("admission_number", "")),
        ("Total Invoiced", f"{statement.get('total_invoiced', 0):.2f}"),
        ("Total Paid", f"{statement.get('total_paid', 0):.2f}"),
        ("Outstanding", f"{statement.get('total_outstanding', 0):.2f}"),
    ]
    return _pdf("Fee Statement", lines)


def receipt_pdf(payment: dict[str, Any], student: dict[str, Any]) -> BytesIO:
    lines = [
        ("Receipt No.", payment.get("receipt_number", "")),
        ("Student", student.get("full_name", "")),
        ("Amount", f"{payment.get('amount', 0):.2f}"),
        ("Method", payment.get("method", "")),
        ("Date", str(payment.get("paid_at", ""))),
        ("Reference", payment.get("reference", "") or "—"),
    ]
    return _pdf("Payment Receipt", lines)


def result_sheet_pdf(exam: dict[str, Any], marks: list[dict[str, Any]]) -> BytesIO:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Result Sheet")
    styles = getSampleStyleSheet()
    flow = [Paragraph(f"Result Sheet — {exam.get('name','')}", styles["Title"]), Spacer(1, 12)]
    data = [["Student", "Marks", "Percentage", "Grade", "Pass"]]
    for m in marks:
        data.append([m.get("student", ""), str(m.get("marks_obtained", "")),
                     str(m.get("percentage", "")), m.get("grade", "") or "—",
                     "Yes" if m.get("is_pass") else "No"])
    flow.append(Table(data))
    doc.build(flow)
    buf.seek(0)
    return buf

"""Report & export routes. Always use authorized DB records."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.examinations import Examination, StudentMark
from app.models.fees import Payment
from app.models.people import Student
from app.models.user import User
from app.schemas.common import Page, paginate
from app.schemas.people import StudentOut
from app.security.dependencies import require_admin, require_staff
from app.services import report_service, fee_service, attendance_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/students.xlsx")
async def students_xlsx(program_id: str | None = Query(None), admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    stmt = select(Student)
    if program_id:
        stmt = stmt.where(Student.current_program_id == program_id)
    rows = (await db.execute(stmt)).scalars().all()
    data = [{"admission_number": r.admission_number, "full_name": r.full_name, "email": r.email,
             "class": str(r.current_class_id), "section": str(r.current_section_id) if r.current_section_id else "",
             "status": r.account_status} for r in rows]
    buf = report_service.students_xlsx(data)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=students.xlsx"})


@router.get("/attendance/class/{class_id}.xlsx")
async def attendance_xlsx(class_id: str, section_id: str | None = Query(None),
                          user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    rows = await attendance_service.class_summary(db, class_id, section_id, None)
    buf = report_service.attendance_xlsx(rows)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=attendance.xlsx"})


@router.get("/fees/{student_id}.pdf")
async def fee_statement_pdf(student_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFoundError("Student not found.")
    statement = await fee_service.student_statement(db, student_id)
    buf = report_service.fee_statement_pdf(
        {"full_name": student.full_name, "admission_number": student.admission_number}, statement
    )
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="fee-{student_id}.pdf"'})


@router.get("/payments/{payment_id}/receipt.pdf")
async def receipt_pdf(payment_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found.")
    student = await db.get(Student, str(payment.student_id))
    buf = report_service.receipt_pdf(
        {"receipt_number": payment.receipt_number, "amount": float(payment.amount),
         "method": payment.method, "paid_at": str(payment.paid_at), "reference": payment.reference},
        {"full_name": student.full_name if student else ""},
    )
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="receipt-{payment.receipt_number}.pdf"'})


@router.get("/examinations/{exam_id}/result-sheet.pdf")
async def result_sheet(exam_id: str, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    exam = await db.get(Examination, exam_id)
    if exam is None:
        raise NotFoundError("Examination not found.")
    marks = (await db.execute(select(StudentMark).where(StudentMark.examination_id == exam_id))).scalars().all()
    data = []
    for m in marks:
        s = await db.get(Student, str(m.student_id))
        data.append({"student": s.full_name if s else str(m.student_id),
                     "marks_obtained": float(m.marks_obtained), "percentage": float(m.percentage or 0),
                     "grade": m.grade, "is_pass": bool(m.is_pass)})
    buf = report_service.result_sheet_pdf({"name": exam.name}, data)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="result-{exam_id}.pdf"'})

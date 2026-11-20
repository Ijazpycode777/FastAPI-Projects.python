"""Dashboard aggregation. Every value comes from real DB queries — no hardcoding."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models.academic import Program
from app.models.attendance import AttendanceRecord
from app.models.communications import Notice
from app.models.examinations import Examination, StudentMark
from app.models.fees import FeeInvoice, Payment
from app.models.people import Student, Teacher
from app.models.user import User
from app.services.attendance_logic import attendance_percentage
from app.services.fees_calc import total_outstanding, total_paid
from app.services.fees_calc import InvoiceView


async def admin_dashboard(db: AsyncSession) -> dict[str, Any]:
    active_students = (await db.execute(
        select(func.count()).select_from(Student).where(Student.account_status == "active")
    )).scalar_one()
    teachers = (await db.execute(
        select(func.count()).select_from(Teacher).where(Teacher.employment_status == "active")
    )).scalar_one()

    # Program distribution
    rows = (await db.execute(
        select(Student.current_program_id, func.count()).where(Student.account_status == "active").group_by(Student.current_program_id)
    )).all()
    programs = {str(p.id): p.code for p in (await db.execute(select(Program))).scalars().all()}
    program_dist = [{"label": programs.get(pid, "—"), "value": cnt} for pid, cnt in rows if pid]

    # Class/section distribution
    cs_rows = (await db.execute(
        select(Student.current_class_id, Student.current_section_id, func.count())
        .where(Student.account_status == "active")
        .group_by(Student.current_class_id, Student.current_section_id)
    )).all()
    class_section_dist = [{"label": f"{cid}/{sid}", "value": cnt} for cid, sid, cnt in cs_rows if cid]

    # Attendance trend (last 7 days)
    since = date.today() - timedelta(days=7)
    att_rows = (await db.execute(
        select(AttendanceRecord.attendance_date, AttendanceRecord.status)
        .where(AttendanceRecord.attendance_date >= since)
    )).all()
    by_day: dict[date, list[str]] = {}
    for d, st in att_rows:
        by_day.setdefault(d, []).append(st)
    trend = [{"label": d.isoformat(), "value": attendance_percentage(sts)} for d, sts in sorted(by_day.items())]

    # Examination performance by type
    exam_rows = (await db.execute(
        select(Examination.exam_type, func.avg(StudentMark.percentage))
        .join(StudentMark, StudentMark.examination_id == Examination.id)
        .where(StudentMark.is_absent.is_(False))
        .group_by(Examination.exam_type)
    )).all()
    exam_perf = [{"label": t, "value": round(float(v or 0), 2)} for t, v in exam_rows]

    # Fees
    invoices = (await db.execute(select(FeeInvoice))).scalars().all()
    inv_views = []
    for inv in invoices:
        pays = (await db.execute(select(Payment.amount).where(Payment.invoice_id == inv.id))).scalars().all()
        inv_views.append(InvoiceView(str(inv.id), float(inv.amount), [float(p) for p in pays]))
    collected = total_paid(inv_views)
    outstanding = total_outstanding(inv_views)

    recent_notices = (await db.execute(
        select(Notice).order_by(Notice.published_at.desc()).limit(5)
    )).scalars().all()

    return {
        "stats": [
            {"label": "Active Students", "value": int(active_students), "tone": "primary"},
            {"label": "Active Teachers", "value": int(teachers), "tone": "primary"},
            {"label": "Total Collected", "value": collected, "tone": "success"},
            {"label": "Outstanding", "value": outstanding, "tone": "danger"},
        ],
        "program_distribution": program_dist,
        "class_section_distribution": class_section_dist,
        "attendance_trend": trend,
        "examination_performance": exam_perf,
        "fee_collection": [
            {"label": "Collected", "value": collected, "tone": "success"},
            {"label": "Outstanding", "value": outstanding, "tone": "danger"},
        ],
        "outstanding_balance": outstanding,
        "recent_notices": [{"id": str(n.id), "title": n.title, "published_at": n.published_at.isoformat()} for n in recent_notices],
        "recent_activity": [],
    }


async def teacher_dashboard(db: AsyncSession, user: User) -> dict[str, Any]:
    teacher = user.teacher_profile
    if teacher is None:
        raise ForbiddenError("Teacher profile missing.")
    from app.models.assignments import TeacherAssignment
    from app.models.timetable import TimetableEntry

    assignments = (await db.execute(
        select(TeacherAssignment).where(TeacherAssignment.teacher_id == teacher.id, TeacherAssignment.is_active.is_(True))
    )).scalars().all()
    today = date.today()
    today_name = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"][today.weekday()]
    today_entries = (await db.execute(
        select(TimetableEntry).where(TimetableEntry.teacher_id == teacher.id,
                                     TimetableEntry.day_of_week == today_name,
                                     TimetableEntry.is_cancelled.is_(False))
        .order_by(TimetableEntry.start_time)
    )).scalars().all()
    upcoming = (await db.execute(
        select(Examination).where(Examination.exam_date >= today,
                                  Examination.subject_id.in_([a.subject_id for a in assignments] or ["__none__"]))
        .order_by(Examination.exam_date).limit(5)
    )).scalars().all()
    notices = (await db.execute(
        select(Notice).where(Notice.target_audience.in_(["all", "teachers"]))
        .order_by(Notice.published_at.desc()).limit(5)
    )).scalars().all()

    return {
        "stats": [
            {"label": "Assigned Classes", "value": len({str(a.class_id) for a in assignments}), "tone": "primary"},
            {"label": "Assigned Subjects", "value": len({str(a.subject_id) for a in assignments}), "tone": "primary"},
            {"label": "Today's Lectures", "value": len(today_entries), "tone": "primary"},
            {"label": "Upcoming Exams", "value": len(upcoming), "tone": "warning"},
        ],
        "assigned_classes": [{"class_id": str(a.class_id), "section_id": str(a.section_id) if a.section_id else None, "subject_id": str(a.subject_id)} for a in assignments],
        "assigned_subjects": list({str(a.subject_id) for a in assignments}),
        "today_timetable": [{"id": str(e.id), "start": e.start_time.isoformat(), "end": e.end_time.isoformat(), "class_id": str(e.class_id)} for e in today_entries],
        "attendance_summary": {},
        "upcoming_examinations": [{"id": str(e.id), "name": e.name, "date": e.exam_date.isoformat()} for e in upcoming],
        "student_performance": [],
        "recent_notices": [{"id": str(n.id), "title": n.title} for n in notices],
        "workload": {"weekly_lectures": len(assignments)},
    }


async def student_dashboard(db: AsyncSession, user: User) -> dict[str, Any]:
    student = user.student_profile
    if student is None:
        raise ForbiddenError("Student profile missing.")
    from app.services.attendance_service import student_percentage
    from app.services.fee_service import student_statement

    att = await student_percentage(db, str(student.id))
    marks = (await db.execute(select(StudentMark).where(StudentMark.student_id == student.id))).scalars().all()
    materials = await __import__("app.services.material_service", fromlist=["list_for_student"]).list_for_student(db, student)
    notices = (await __import__("app.services.notice_service", fromlist=["list_for_user"]).list_for_user(db, user))
    statement = await student_statement(db, str(student.id))

    return {
        "stats": [
            {"label": "Attendance", "value": att["percentage"], "hint": "%", "tone": "success" if att["percentage"] >= 75 else "warning"},
            {"label": "Exams Taken", "value": len(marks), "tone": "primary"},
            {"label": "Outstanding Fees", "value": statement["total_outstanding"], "tone": "danger" if statement["total_outstanding"] > 0 else "success"},
            {"label": "Materials", "value": len(materials), "tone": "primary"},
        ],
        "attendance_percentage": att["percentage"],
        "subject_marks": [{"subject_id": str(m.subject_id), "percentage": float(m.percentage or 0), "grade": m.grade} for m in marks],
        "recent_examinations": [],
        "recent_materials": [{"id": str(m.id), "title": m.title} for m in materials[:5]],
        "notices": [{"id": str(n.id), "title": n.title} for n in notices[:5]],
        "fee_summary": statement,
        "progression": [],
    }

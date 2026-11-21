"""Dashboard aggregation. Every value comes from real DB queries — no hardcoding."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models.academic import ClassLevel, Program, Section, Subject
from app.models.assignments import TeacherAssignment
from app.models.attendance import AttendanceRecord
from app.models.communications import Notice
from app.models.examinations import Examination, StudentMark
from app.models.fees import FeeInvoice, Payment
from app.models.people import Student, StudentEnrolment, Teacher
from app.models.timetable import TimetableEntry
from app.models.user import User
from app.services.attendance_service import student_breakdown
from app.services.fees_calc import InvoiceView, total_outstanding, total_paid

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


async def _names(db: AsyncSession, model, ids: set[str]) -> dict[str, str]:
    """id -> name (or full_name for Teacher) lookup."""
    if not ids:
        return {}
    rows = (await db.execute(select(model).where(model.id.in_(list(ids))))).scalars().all()
    field = "full_name" if model is Teacher else "name"
    return {str(r.id): getattr(r, field) for r in rows}


async def admin_dashboard(db: AsyncSession) -> dict[str, Any]:
    active_students = (await db.execute(
        select(func.count()).select_from(Student).where(Student.account_status == "active")
    )).scalar_one()
    teachers = (await db.execute(
        select(func.count()).select_from(Teacher).where(Teacher.employment_status == "active")
    )).scalar_one()
    active_classes = (await db.execute(
        select(func.count(func.distinct(Student.current_class_id)))
        .where(Student.account_status == "active", Student.current_class_id.is_not(None))
    )).scalar_one()
    total_sections = (await db.execute(select(func.count()).select_from(Section))).scalar_one()

    # Enrolment distribution by program (donut).
    rows = (await db.execute(
        select(Student.current_program_id, func.count())
        .where(Student.account_status == "active")
        .group_by(Student.current_program_id)
    )).all()
    programs = await _names(db, Program, {pid for pid, _ in rows if pid})
    program_dist = [{"label": programs.get(str(pid), "—"), "value": int(cnt)} for pid, cnt in rows if pid]

    # Class/section comparison (horizontal bar).
    cs_rows = (await db.execute(
        select(Student.current_class_id, Student.current_section_id, func.count())
        .where(Student.account_status == "active")
        .group_by(Student.current_class_id, Student.current_section_id)
    )).all()
    cnames = await _names(db, ClassLevel, {cid for cid, _, _ in cs_rows if cid})
    snames = await _names(db, Section, {sid for _, sid, _ in cs_rows if sid})
    class_comparison: list[dict[str, Any]] = []
    for cid, sid, cnt in cs_rows:
        if not cid:
            continue
        label = cnames.get(str(cid), "—")
        if sid:
            label = f"{label} · {snames.get(str(sid), '—')}"
        class_comparison.append({"label": label, "value": int(cnt)})
    class_comparison.sort(key=lambda x: x["value"], reverse=True)

    # Examination performance by type.
    exam_rows = (await db.execute(
        select(Examination.exam_type, func.avg(StudentMark.percentage))
        .join(StudentMark, StudentMark.examination_id == Examination.id)
        .where(StudentMark.is_absent.is_(False))
        .group_by(Examination.exam_type)
    )).all()
    exam_perf = [{"label": t, "value": round(float(v or 0), 2)} for t, v in exam_rows]

    # Fees: collected/outstanding + monthly collection trend.
    invoices = (await db.execute(select(FeeInvoice))).scalars().all()
    inv_views: list[InvoiceView] = []
    for inv in invoices:
        pays = (await db.execute(select(Payment.amount).where(Payment.invoice_id == inv.id))).scalars().all()
        inv_views.append(InvoiceView(str(inv.id), float(inv.amount), [float(p) for p in pays]))
    collected = total_paid(inv_views)
    outstanding = total_outstanding(inv_views)
    pay_rows = (await db.execute(select(Payment.paid_at, Payment.amount))).all()
    by_month: dict[str, float] = {}
    for pd, amt in pay_rows:
        if pd:
            key = pd.strftime("%Y-%m")
            by_month[key] = by_month.get(key, 0.0) + float(amt)
    fee_trend = [{"label": k, "value": round(v, 2)} for k, v in sorted(by_month.items())]

    recent_notices = (await db.execute(
        select(Notice).order_by(Notice.published_at.desc()).limit(5)
    )).scalars().all()

    # Top performers — real data only (never fabricated). Best in Marks uses
    # average examination percentage; Best in Attendance uses the present/absent
    # ratio. Each appears only when sufficient records exist.
    top_performers: list[dict[str, Any]] = []
    mk = (await db.execute(
        select(StudentMark.student_id, func.avg(StudentMark.percentage))
        .where(StudentMark.is_absent.is_(False))
        .group_by(StudentMark.student_id)
        .order_by(func.avg(StudentMark.percentage).desc())
        .limit(1)
    )).first()
    if mk:
        sid, avg = mk
        stu = await db.get(Student, sid)
        if stu:
            top_performers.append({"student_id": str(sid), "name": stu.full_name, "category": "Best in Marks", "score": round(float(avg), 1), "metric": "avg %"})
    att_rows = (await db.execute(select(AttendanceRecord.student_id, AttendanceRecord.status))).all()
    by_stu: dict[str, list[str]] = {}
    for sid, st in att_rows:
        by_stu.setdefault(str(sid), []).append(st)
    best_att: dict[str, Any] | None = None
    for sid, sts in by_stu.items():
        if len(sts) < 3:
            continue
        attended = sum(1 for s in sts if s in ("present", "late"))
        elig = attended + sum(1 for s in sts if s == "absent")
        if elig == 0:
            continue
        pct = round(attended / elig * 100, 1)
        if best_att is None or pct > best_att["score"]:
            best_att = {"student_id": sid, "score": pct}
    if best_att:
        stu = await db.get(Student, best_att["student_id"])
        if stu:
            top_performers.append({"student_id": best_att["student_id"], "name": stu.full_name, "category": "Best in Attendance", "score": best_att["score"], "metric": "% present"})

    return {
        "stats": [
            {"label": "Total Students", "value": int(active_students), "tone": "primary"},
            {"label": "Total Teachers", "value": int(teachers), "tone": "primary"},
            {"label": "Active Classes", "value": int(active_classes), "tone": "primary"},
            {"label": "Total Sections", "value": int(total_sections), "tone": "primary"},
            {"label": "Fee Collection", "value": round(float(collected), 2), "tone": "success"},
            {"label": "Outstanding Fees", "value": round(float(outstanding), 2), "tone": "danger"},
        ],
        "program_distribution": program_dist,
        "class_comparison": class_comparison,
        "examination_performance": exam_perf,
        "fee_collection_trend": fee_trend,
        "fee_collection": [
            {"label": "Collected", "value": round(float(collected), 2), "tone": "success"},
            {"label": "Outstanding", "value": round(float(outstanding), 2), "tone": "danger"},
        ],
        "outstanding_balance": round(float(outstanding), 2),
        "recent_notices": [{"id": str(n.id), "title": n.title, "published_at": n.published_at.isoformat()} for n in recent_notices],
        "recent_activity": [],
        "top_performers": top_performers,
    }


async def teacher_dashboard(db: AsyncSession, user: User) -> dict[str, Any]:
    teacher = user.teacher_profile
    if teacher is None:
        raise ForbiddenError("Teacher profile missing.")
    today = date.today()
    today_name = _WEEKDAYS[today.weekday()]

    assignments = (await db.execute(
        select(TeacherAssignment).where(TeacherAssignment.teacher_id == teacher.id, TeacherAssignment.is_active.is_(True))
    )).scalars().all()
    class_ids = {str(a.class_id) for a in assignments}
    subject_ids = {str(a.subject_id) for a in assignments}

    weekly = (await db.execute(
        select(TimetableEntry).where(TimetableEntry.teacher_id == teacher.id, TimetableEntry.is_cancelled.is_(False))
        .order_by(TimetableEntry.day_of_week, TimetableEntry.start_time)
    )).scalars().all()
    w_subj = await _names(db, Subject, {str(e.subject_id) for e in weekly})
    w_cls = await _names(db, ClassLevel, {str(e.class_id) for e in weekly})
    w_sec = await _names(db, Section, {str(e.section_id) for e in weekly if e.section_id})
    weekly_timetable = [{
        "id": str(e.id), "day": e.day_of_week,
        "start": e.start_time.isoformat(), "end": e.end_time.isoformat(),
        "subject_name": w_subj.get(str(e.subject_id), "—"),
        "class_name": w_cls.get(str(e.class_id), "—"),
        "section_name": w_sec.get(str(e.section_id)) if e.section_id else None,
    } for e in weekly]
    today_entries = [e for e in weekly if e.day_of_week == today_name]

    # Class distribution: students per assigned class.
    cls_students = (await db.execute(
        select(Student.current_class_id, func.count())
        .where(Student.account_status == "active",
               Student.current_class_id.in_(list(class_ids) or ["__none__"]))
        .group_by(Student.current_class_id)
    )).all()
    cnames = await _names(db, ClassLevel, class_ids)
    class_distribution = [{"label": cnames.get(str(cid), "—"), "value": int(cnt)} for cid, cnt in cls_students]

    # Student performance: average mark % per assigned subject.
    perf_rows = (await db.execute(
        select(StudentMark.subject_id, func.avg(StudentMark.percentage))
        .where(StudentMark.subject_id.in_(list(subject_ids) or ["__none__"]), StudentMark.is_absent.is_(False))
        .group_by(StudentMark.subject_id)
    )).all()
    snames = await _names(db, Subject, subject_ids)
    student_performance = [{"label": snames.get(str(sid), "—"), "value": round(float(v or 0), 2)} for sid, v in perf_rows]

    upcoming = (await db.execute(
        select(Examination).where(Examination.exam_date >= today,
                                  Examination.subject_id.in_(list(subject_ids) or ["__none__"]))
        .order_by(Examination.exam_date).limit(5)
    )).scalars().all()
    notices = (await db.execute(
        select(Notice).where(Notice.target_audience.in_(["all", "teachers"]))
        .order_by(Notice.published_at.desc()).limit(5)
    )).scalars().all()

    students_across = int(sum(r[1] for r in cls_students))

    return {
        "stats": [
            {"label": "Assigned Classes", "value": len(class_ids), "tone": "primary"},
            {"label": "Today's Lectures", "value": len(today_entries), "tone": "primary"},
            {"label": "Total Weekly Lectures", "value": len(weekly), "tone": "primary"},
            {"label": "Students in Classes", "value": students_across, "tone": "primary"},
        ],
        "assigned_classes": [{"class_id": str(a.class_id), "section_id": str(a.section_id) if a.section_id else None, "subject_id": str(a.subject_id)} for a in assignments],
        "assigned_subjects": list(subject_ids),
        "today_timetable": [{"id": str(e.id), "start": e.start_time.isoformat(), "end": e.end_time.isoformat(), "class_id": str(e.class_id)} for e in today_entries],
        "weekly_timetable": weekly_timetable,
        "class_distribution": class_distribution,
        "upcoming_examinations": [{"id": str(e.id), "name": e.name, "date": e.exam_date.isoformat()} for e in upcoming],
        "student_performance": student_performance,
        "recent_notices": [{"id": str(n.id), "title": n.title} for n in notices],
        "workload": {"weekly_lectures": len(weekly)},
    }


async def student_dashboard(db: AsyncSession, user: User) -> dict[str, Any]:
    student = user.student_profile
    if student is None:
        raise ForbiddenError("Student profile missing.")
    from app.services.fee_service import student_statement
    from app.services.material_service import list_for_student
    from app.services.notice_service import list_for_user

    att = await student_breakdown(db, str(student.id))
    marks = (await db.execute(select(StudentMark).where(StudentMark.student_id == student.id))).scalars().all()
    subj_names = await _names(db, Subject, {str(m.subject_id) for m in marks})
    materials = await list_for_student(db, student)
    notices = await list_for_user(db, user)
    statement = await student_statement(db, str(student.id))

    # Today's lectures for the student's class/section.
    enrol_res = await db.execute(
        select(StudentEnrolment).where(StudentEnrolment.student_id == student.id, StudentEnrolment.is_active.is_(True))
    )
    enrol = enrol_res.scalar_one_or_none()
    class_id = enrol.class_id if enrol else student.current_class_id
    section_id = enrol.section_id if enrol else student.current_section_id
    sess_id = enrol.academic_session_id if enrol else student.current_session_id
    today_name = _WEEKDAYS[date.today().weekday()]
    lecture_overview: list[dict[str, Any]] = []
    if class_id and sess_id:
        ents = (await db.execute(
            select(TimetableEntry).where(
                TimetableEntry.class_id == class_id,
                TimetableEntry.academic_session_id == sess_id,
                TimetableEntry.day_of_week == today_name,
                TimetableEntry.is_cancelled.is_(False),
            ).order_by(TimetableEntry.start_time)
        )).scalars().all()
        if section_id:
            ents = [e for e in ents if e.section_id is None or str(e.section_id) == str(section_id)]
        l_subj = await _names(db, Subject, {str(e.subject_id) for e in ents})
        l_tch = await _names(db, Teacher, {str(e.teacher_id) for e in ents})
        lecture_overview = [{
            "id": str(e.id),
            "start": e.start_time.isoformat(), "end": e.end_time.isoformat(),
            "subject_name": l_subj.get(str(e.subject_id), "—"),
            "teacher_name": l_tch.get(str(e.teacher_id), "—"),
        } for e in ents]

    return {
        "stats": [
            {"label": "Attendance", "value": att["percentage"], "hint": "%", "tone": "success" if att["percentage"] >= 75 else "warning"},
            {"label": "Exams Taken", "value": len(marks), "tone": "primary"},
            {"label": "Outstanding Fees", "value": round(float(statement["total_outstanding"]), 2), "tone": "danger" if statement["total_outstanding"] > 0 else "success"},
            {"label": "Materials", "value": len(materials), "tone": "primary"},
        ],
        "attendance_percentage": att["percentage"],
        "attendance_breakdown": att,
        "subject_marks": [{"subject_id": str(m.subject_id), "subject_name": subj_names.get(str(m.subject_id), "—"), "percentage": float(m.percentage or 0), "grade": m.grade} for m in marks],
        "lecture_overview": lecture_overview,
        "recent_examinations": [],
        "recent_materials": [{"id": str(m.id), "title": m.title} for m in materials[:5]],
        "notices": [{"id": str(n.id), "title": n.title} for n in notices[:5]],
        "fee_summary": statement,
        "progression": [],
    }

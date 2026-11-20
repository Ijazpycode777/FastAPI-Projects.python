"""API v1 router aggregator."""
from fastapi import APIRouter

from app.api.v1 import (
    academic,
    attendance,
    audit,
    auth,
    dashboard,
    examinations,
    fees,
    grading,
    materials,
    notices,
    reports,
    students,
    teacher_attendance,
    teachers,
    timetable,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(academic.router)
api_router.include_router(students.router)
api_router.include_router(teachers.router)
api_router.include_router(timetable.router)
api_router.include_router(attendance.router)
api_router.include_router(teacher_attendance.router)
api_router.include_router(examinations.router)
api_router.include_router(grading.router)
api_router.include_router(fees.router)
api_router.include_router(materials.router)
api_router.include_router(notices.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(audit.router)

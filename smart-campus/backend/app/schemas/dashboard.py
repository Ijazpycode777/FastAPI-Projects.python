"""Dashboard aggregate schemas. All values are computed from real DB data."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StatCard(BaseModel):
    label: str
    value: int | float
    hint: str | None = None
    tone: str = "neutral"  # neutral | success | warning | danger | primary


class SeriesPoint(BaseModel):
    label: str
    value: float | int


class DistributionPoint(BaseModel):
    label: str
    value: int | float
    color: str | None = None


class AdminDashboard(BaseModel):
    stats: list[StatCard]
    program_distribution: list[DistributionPoint]      # enrolment donut
    class_comparison: list[DistributionPoint]          # horizontal bar
    examination_performance: list[SeriesPoint]         # avg % per exam type
    fee_collection_trend: list[SeriesPoint]            # monthly collected amount
    fee_collection: list[StatCard]
    outstanding_balance: float
    recent_notices: list[dict[str, Any]]
    recent_activity: list[dict[str, Any]]
    top_performers: list[dict[str, Any]]   # achievement cards (real data only)


class TeacherDashboard(BaseModel):
    stats: list[StatCard]
    assigned_classes: list[dict[str, Any]]
    assigned_subjects: list[dict[str, Any]]
    today_timetable: list[dict[str, Any]]
    weekly_timetable: list[dict[str, Any]]             # full week, with names
    class_distribution: list[DistributionPoint]        # students per assigned class
    upcoming_examinations: list[dict[str, Any]]
    student_performance: list[dict[str, Any]]          # avg % per subject
    recent_notices: list[dict[str, Any]]
    workload: dict[str, Any]


class StudentDashboard(BaseModel):
    stats: list[StatCard]
    attendance_percentage: float
    attendance_breakdown: dict[str, Any]               # present/absent/leave donut
    subject_marks: list[dict[str, Any]]
    lecture_overview: list[dict[str, Any]]             # today's lectures
    recent_examinations: list[dict[str, Any]]
    recent_materials: list[dict[str, Any]]
    notices: list[dict[str, Any]]
    fee_summary: dict[str, Any]
    progression: list[dict[str, Any]]

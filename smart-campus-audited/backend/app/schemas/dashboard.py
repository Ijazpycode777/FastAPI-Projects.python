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
    program_distribution: list[DistributionPoint]
    class_section_distribution: list[DistributionPoint]
    attendance_trend: list[SeriesPoint]            # last 7 working days
    examination_performance: list[SeriesPoint]     # average % per exam type
    fee_collection: list[StatCard]
    outstanding_balance: float
    recent_notices: list[dict[str, Any]]
    recent_activity: list[dict[str, Any]]


class TeacherDashboard(BaseModel):
    stats: list[StatCard]
    assigned_classes: list[dict[str, Any]]
    assigned_subjects: list[dict[str, Any]]
    today_timetable: list[dict[str, Any]]
    attendance_summary: dict[str, Any]
    upcoming_examinations: list[dict[str, Any]]
    student_performance: list[dict[str, Any]]
    recent_notices: list[dict[str, Any]]
    workload: dict[str, Any]


class StudentDashboard(BaseModel):
    stats: list[StatCard]
    attendance_percentage: float
    subject_marks: list[dict[str, Any]]
    recent_examinations: list[dict[str, Any]]
    recent_materials: list[dict[str, Any]]
    notices: list[dict[str, Any]]
    fee_summary: dict[str, Any]
    progression: list[dict[str, Any]]

"""Notification audience targeting (pure logic).

A user receives a notice if the audience rule matches their role/placement.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AudienceTarget:
    target_audience: str
    program_id: str | None
    class_id: str | None
    section_id: str | None


@dataclass
class Recipient:
    user_id: str
    role: str
    program_id: str | None
    class_id: str | None
    section_id: str | None


def matches(target: AudienceTarget, r: Recipient) -> bool:
    aud = target.target_audience
    if aud == "all":
        return True
    if aud == "admins":
        return r.role == "admin"
    if aud == "teachers":
        return r.role == "teacher"
    if aud == "students":
        return r.role == "student"
    if aud == "program":
        return r.role == "student" and r.program_id == target.program_id
    if aud == "class":
        return r.role == "student" and r.class_id == target.class_id
    if aud == "section":
        return (
            r.role == "student"
            and r.class_id == target.class_id
            and r.section_id == target.section_id
        )
    return False


def filter_recipients(target: AudienceTarget, recipients: list[Recipient]) -> list[Recipient]:
    return [r for r in recipients if matches(target, r)]

"""General-purpose helpers used across the codebase."""
from __future__ import annotations

import os
import re
import secrets
import string
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

from app.core.config import settings

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def slugify(value: str) -> str:
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-")


def generate_password(length: int = 12) -> str:
    """Generate a one-time reset password that satisfies strength rules."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        from app.security.password import is_strong_password

        ok, _ = is_strong_password(pw)
        if ok:
            return pw


def admission_number_year_prefix(d: date | None = None) -> str:
    d = d or date.today()
    return f"SC-{d.year}"


def next_roll_number(existing: Sequence[int]) -> int:
    """Smallest positive integer not in ``existing``."""
    taken = set(existing)
    i = 1
    while i in taken:
        i += 1
    return i


def safe_filename(name: str) -> str:
    """Strip path separators and dangerous characters; keep extension."""
    base = os.path.basename(name).strip()
    base = re.sub(r"[^\w.\- ]+", "_", base)
    return base[:120] or "upload"


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def chunks(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    bucket: list[Any] = []
    for item in items:
        bucket.append(item)
        if len(bucket) == size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


def date_range(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def sql_in(values: Sequence[str]) -> str:
    """Build a SQL ``IN (...)`` list with properly quoted string literals."""
    return "(" + ",".join(f"'{v}'" for v in values) + ")"

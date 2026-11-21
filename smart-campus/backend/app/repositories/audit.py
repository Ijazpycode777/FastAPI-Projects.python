"""Audit logging helper. Append-only; records before/after JSON snapshots."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.utils.helpers import now_utc

_log = logging.getLogger("smartcampus")

# Columns that must never be written to the audit log, even defensively.
_SENSITIVE_COLUMNS = frozenset({"password_hash", "token", "session_token", "csrf_token"})


async def record_audit(
    db: AsyncSession,
    *,
    actor_id: str | None,
    actor_role: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    before: Any = None,
    after: Any = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog | None:
    def _dump(v: Any) -> str | None:
        if v is None:
            return None
        try:
            return json.dumps(v, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(v)

    entry = AuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=_dump(before),
        after=_dump(after),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    # The audit log records an action that has ALREADY happened (the caller
    # flushed the business object — e.g. the new student — before calling
    # us). It is a non-critical, append-only record and must NEVER break the
    # business operation it describes. Writing it inside a SAVEPOINT isolates the
    # audit insert: if it fails for any reason (missing/stale table, FK or DB
    # error, unique violation) only the audit row is rolled back — the caller's
    # transaction (and the business object it already created) stays intact and
    # commits. The failure is logged loudly so it is never silently swallowed.
    try:
        async with db.begin_nested():
            db.add(entry)
            await db.flush()
    except Exception:  # noqa: BLE001 — best-effort: never propagate audit failures
        _log.exception(
            "Audit log write failed for action=%s resource=%s resource_id=%s; "
            "the business operation succeeded but is not recorded in the audit log.",
            action, resource_type, resource_id,
        )
        return None
    return entry


async def snapshot(model: Any) -> dict[str, Any]:
    """Best-effort JSON-serializable snapshot of a model instance.

    Sensitive columns (password hashes, tokens) are always redacted so they can
    never leak into the audit log, even if a caller snapshots a User/Session.
    """
    if model is None:
        return {}
    out: dict[str, Any] = {}
    for col in model.__table__.columns:  # type: ignore[attr-defined]
        if col.name in _SENSITIVE_COLUMNS:
            out[col.name] = "[REDACTED]"
            continue
        try:
            out[col.name] = getattr(model, col.name)
        except AttributeError:
            continue
    return out

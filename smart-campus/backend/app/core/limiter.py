"""Shared SlowAPI limiter instance.

Lives in its own module so that both the application factory (``app.main``) and
route modules (e.g. ``app.api.v1.auth``) can import the same singleton without
a circular import: ``app.main`` imports the routers, which would otherwise be
unable to import ``limiter`` from ``app.main``.
"""
from __future__ import annotations

from __future__ import annotations

import inspect
import typing

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.default_rate_limit],
)


def rate_limit(limit_value):
    """Decorator applying SlowAPI rate limiting while keeping FastAPI happy.

    ``slowapi``'s wrapper uses ``functools.wraps``. ``inspect.signature`` on the
    wrapped function follows ``__wrapped__`` back to the ORIGINAL function, so it
    returns the original signature — whose annotations are *strings* (PEP 563,
    ``from __future__ import annotations``) like ``'LoginIn'``. FastAPI resolves
    those strings via ``typing.get_type_hints`` using the WRAPPED function's
    ``__globals__`` (this module), where the endpoint's types are not imported —
    so resolution fails and a ``payload: LoginIn`` parameter is mis-classified as
    a query param (the body is never parsed -> 422 "payload: Field required").

    The fix: resolve the original annotations to concrete types with
    ``typing.get_type_hints`` (using the original function's globals) and assign
    a fully-resolved signature to the wrapper's ``__signature__``, which
    ``inspect.signature`` prefers over following ``__wrapped__``.
    """
    def decorator(func):
        wrapped = limiter.limit(limit_value)(func)
        try:
            sig = inspect.signature(func)
            hints = typing.get_type_hints(func)
            resolved = [
                p.replace(annotation=hints.get(name, p.annotation))
                for name, p in sig.parameters.items()
            ]
            wrapped.__signature__ = sig.replace(parameters=resolved)
            wrapped.__annotations__ = hints
        except Exception:  # pragma: no cover - fall back to SlowAPI's wrapper
            pass
        return wrapped

    return decorator

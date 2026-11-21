"""Centralized, structured API error model and HTTP exception mapping.

Every API error response follows this envelope:

    {
      "error": {
        "code": "VALIDATION_ERROR",
        "message": "Human readable summary",
        "details": [{"field": "email", "message": "..."}],
        "request_id": "..."
      }
    }

Internal stack traces are never exposed to clients.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

log = logging.getLogger("smartcampus.errors")

# Stable error codes used across the API.
ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


class AppException(Exception):
    """Domain-level exception carrying a stable error code and HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: Optional[str] = None,
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or ERROR_CODES.get(status_code, "BAD_REQUEST")
        self.details = details or []


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", **kw: Any) -> None:
        super().__init__(message, status_code=404, code="NOT_FOUND", **kw)


class ConflictError(AppException):
    def __init__(self, message: str, **kw: Any) -> None:
        super().__init__(message, status_code=409, code="CONFLICT", **kw)


class ForbiddenError(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action.", **kw: Any) -> None:
        super().__init__(message, status_code=403, code="FORBIDDEN", **kw)


class UnauthenticatedError(AppException):
    def __init__(self, message: str = "Authentication required.", **kw: Any) -> None:
        super().__init__(message, status_code=401, code="UNAUTHENTICATED", **kw)


class ValidationError(AppException):
    def __init__(self, message: str = "Validation failed", details: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(message, status_code=422, code="VALIDATION_ERROR", details=details)


def _envelope(code: str, message: str, details: Optional[List[Dict[str, Any]]], request_id: str) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": request_id,
        }
    }


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _app_exc(request: Request, exc: AppException) -> JSONResponse:
        if exc.status_code >= 500:
            log.exception("AppException %s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(_envelope(exc.code, exc.message, exc.details, _request_id(request))),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
        detail = getattr(exc, "detail", "HTTP error")
        if isinstance(detail, dict):
            message = detail.get("message", "HTTP error")
            details = detail.get("details")
        else:
            message = str(detail)
            details = None
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(_envelope(code, message, details, _request_id(request))),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path"))
            details.append({"field": loc or "_", "message": err.get("msg", "invalid")})
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                _envelope("VALIDATION_ERROR", "Request validation failed.", details, _request_id(request))
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled server error: %s", exc)
        # In production the client sees only a generic message (no internal
        # detail leaks). In development/staging the exception type + message are
        # surfaced so the failure is diagnosable from the UI instead of an
        # opaque "unexpected error" (the full traceback is always in the logs).
        if settings.app_env == "production":
            message = "An unexpected error occurred. Please try again later."
        else:
            message = f"Server error: {type(exc).__name__}: {exc}"
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder(
                _envelope("INTERNAL_ERROR", message, None, _request_id(request))
            ),
        )


def _request_id(request: Request) -> str:
    # RequestIdMiddleware stores the id on request.state; fall back to a header
    # if present. Never empty when the middleware has run.
    rid = getattr(request.state, "request_id", None)
    if rid:
        return rid
    return request.headers.get("x-request-id") or ""

"""Common schema primitives shared across the API."""
from __future__ import annotations

from typing import Generic, List, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagination(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
    total: int = 0
    total_pages: int = 0


class Page(BaseModel, Generic[T]):
    items: List[T]
    pagination: Pagination


class MessageOut(BaseModel):
    message: str
    detail: dict | None = None


def paginate(items: Sequence[T], page: int, page_size: int, total: int) -> Page[T]:
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return Page[T](
        items=list(items),
        pagination=Pagination(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: List[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorEnvelope

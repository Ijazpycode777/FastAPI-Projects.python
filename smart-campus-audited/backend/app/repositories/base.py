"""Generic async repository with paging, filtering and soft helpers.

Repositories stay thin: data access only. Business rules live in services.
"""
from __future__ import annotations

from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: Type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, id_: str) -> ModelT | None:
        result = await self.db.execute(select(self.model).where(self.model.id == id_))  # type: ignore[attr-defined]
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        filters: Sequence[Any] | None = None,
        order_by: Any | None = None,
    ) -> tuple[list[ModelT], int]:
        stmt = select(self.model)
        count_stmt = select(func.count()).select_from(self.model)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
                count_stmt = count_stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(self.model.created_at.desc())  # type: ignore[attr-defined]
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(rows), int(total or 0)

    async def create(self, **kwargs: Any) -> ModelT:
        obj = self.model(**kwargs)  # type: ignore[call-arg]
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ModelT, **kwargs: Any) -> ModelT:
        for k, v in kwargs.items():
            setattr(obj, k, v)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.db.delete(obj)
        await self.db.flush()

    async def commit(self) -> None:
        await self.db.commit()

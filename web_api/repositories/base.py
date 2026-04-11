"""
Repository base class implementing generic CRUD operations.
"""

from typing import TypeVar, Generic, Type, Optional, Sequence, Any, cast
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from web_api.db.database import Base

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic repository for CRUD operations."""

    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, **kwargs: Any) -> T:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: int) -> Optional[T]:
        result = await self.session.execute(
            select(self.model).where(cast(Any, self.model).id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self, skip: int = 0, limit: int = 100, order_by: Optional[Any] = None
    ) -> Sequence[T]:
        query = select(self.model)
        if order_by is not None:
            query = query.order_by(order_by)
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()

    async def delete(self, id: int) -> bool:
        result = await self.session.execute(
            delete(self.model).where(cast(Any, self.model).id == id)
        )
        return cast(int, getattr(cast(Any, result), "rowcount", 0)) > 0

"""Base repository with generic CRUD operations."""

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository providing common CRUD operations."""

    def __init__(self, db: AsyncSession, model: type[T]) -> None:
        """Initialize repository with database session and model class."""
        self.db = db
        self.model = model

    async def get(self, id: int) -> T | None:
        """Get entity by ID."""
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[T]:
        """Get all entities with pagination."""
        result = await self.db.execute(select(self.model).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        """Create a new entity."""
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity: T) -> None:
        """Delete an entity."""
        await self.db.delete(entity)
        await self.db.flush()

    async def count(self) -> int:
        """Count total entities."""
        from sqlalchemy import func

        result = await self.db.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

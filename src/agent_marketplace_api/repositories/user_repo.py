"""User repository for user-specific data access."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import User
from agent_marketplace_api.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with specialized queries."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize user repository."""
        super().__init__(db, User)

    async def find_by_github_id(self, github_id: int) -> User | None:
        """Find user by GitHub ID."""
        result = await self.db.execute(select(User).where(User.github_id == github_id))
        return result.scalar_one_or_none()

    async def find_by_username(self, username: str) -> User | None:
        """Find user by username."""
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> User | None:
        """Find user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

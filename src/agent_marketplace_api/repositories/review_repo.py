"""Review repository for data access."""


from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_marketplace_api.models.agent import Agent
from agent_marketplace_api.models.review import Review
from agent_marketplace_api.models.user import agent_stars
from agent_marketplace_api.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    """Repository for review operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with database session."""
        super().__init__(db, Review)

    async def get_by_agent_and_user(
        self, agent_id: int, user_id: int
    ) -> Review | None:
        """Get a review by agent and user (unique constraint)."""
        result = await self.db.execute(
            select(Review)
            .where(Review.agent_id == agent_id, Review.user_id == user_id)
            .options(selectinload(Review.user))
        )
        return result.scalar_one_or_none()

    async def get_reviews_for_agent(
        self,
        agent_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: str = "helpful",
    ) -> list[Review]:
        """Get reviews for an agent with pagination and sorting.

        Args:
            agent_id: Agent ID
            limit: Maximum number of results
            offset: Number of results to skip
            sort: Sort order (helpful, recent, rating)

        Returns:
            List of reviews
        """
        query = (
            select(Review)
            .where(Review.agent_id == agent_id)
            .options(selectinload(Review.user))
        )

        # Apply sorting
        if sort == "recent":
            query = query.order_by(Review.created_at.desc())
        elif sort == "rating":
            query = query.order_by(Review.rating.desc(), Review.created_at.desc())
        else:  # helpful (default)
            query = query.order_by(Review.helpful_count.desc(), Review.created_at.desc())

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_for_agent(self, agent_id: int) -> int:
        """Count reviews for an agent."""
        result = await self.db.execute(
            select(func.count()).select_from(Review).where(Review.agent_id == agent_id)
        )
        return result.scalar_one()

    async def get_average_rating(self, agent_id: int) -> float:
        """Get average rating for an agent."""
        result = await self.db.execute(
            select(func.avg(Review.rating)).where(Review.agent_id == agent_id)
        )
        avg = result.scalar_one()
        return float(avg) if avg else 0.0

    async def increment_helpful(self, review_id: int) -> None:
        """Increment helpful count for a review."""
        review = await self.get(review_id)
        if review:
            review.helpful_count += 1
            await self.db.flush()

    async def get_with_user(self, review_id: int) -> Review | None:
        """Get review with user relationship loaded."""
        result = await self.db.execute(
            select(Review)
            .where(Review.id == review_id)
            .options(selectinload(Review.user))
        )
        return result.scalar_one_or_none()


class StarRepository:
    """Repository for agent star operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.db = db

    async def is_starred(self, user_id: int, agent_id: int) -> bool:
        """Check if a user has starred an agent."""
        result = await self.db.execute(
            select(agent_stars).where(
                agent_stars.c.user_id == user_id,
                agent_stars.c.agent_id == agent_id,
            )
        )
        return result.first() is not None

    async def add_star(self, user_id: int, agent_id: int) -> bool:
        """Add a star to an agent.

        Returns:
            True if star was added, False if already starred
        """
        if await self.is_starred(user_id, agent_id):
            return False

        await self.db.execute(
            agent_stars.insert().values(user_id=user_id, agent_id=agent_id)
        )
        await self.db.flush()
        return True

    async def remove_star(self, user_id: int, agent_id: int) -> bool:
        """Remove a star from an agent.

        Returns:
            True if star was removed, False if not starred
        """
        from typing import cast

        from sqlalchemy.engine import CursorResult

        result = cast(
            CursorResult[tuple[()]],
            await self.db.execute(
                delete(agent_stars).where(
                    agent_stars.c.user_id == user_id,
                    agent_stars.c.agent_id == agent_id,
                )
            ),
        )
        await self.db.flush()
        return result.rowcount > 0

    async def count_stars(self, agent_id: int) -> int:
        """Count stars for an agent."""
        result = await self.db.execute(
            select(func.count())
            .select_from(agent_stars)
            .where(agent_stars.c.agent_id == agent_id)
        )
        return result.scalar_one()

    async def get_starred_agents(
        self, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[Agent]:
        """Get agents starred by a user."""
        result = await self.db.execute(
            select(Agent)
            .join(agent_stars, Agent.id == agent_stars.c.agent_id)
            .where(agent_stars.c.user_id == user_id)
            .order_by(agent_stars.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_agent_star_count(self, agent_id: int) -> None:
        """Update the star count on an agent."""
        count = await self.count_stars(agent_id)
        result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent:
            agent.stars = count
            await self.db.flush()

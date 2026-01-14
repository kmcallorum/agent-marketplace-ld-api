"""Agent repository for agent-specific data access."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_marketplace_api.models import Agent
from agent_marketplace_api.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    """Repository for Agent model with specialized queries."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize agent repository."""
        super().__init__(db, Agent)

    async def find_by_slug(self, slug: str) -> Agent | None:
        """Find agent by slug."""
        result = await self.db.execute(
            select(Agent)
            .where(Agent.slug == slug)
            .options(selectinload(Agent.author), selectinload(Agent.versions))
        )
        return result.scalar_one_or_none()

    async def find_by_author(
        self, author_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[Agent]:
        """Find all agents by author ID."""
        result = await self.db.execute(
            select(Agent)
            .where(Agent.author_id == author_id)
            .options(selectinload(Agent.author))
            .order_by(Agent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_public(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        category: str | None = None,
        sort_by: str = "created_at",
    ) -> list[Agent]:
        """List public agents with optional filtering and sorting."""
        query = select(Agent).where(Agent.is_public.is_(True))

        if category:
            from agent_marketplace_api.models import Category, agent_categories

            # Use exists subquery to avoid duplicates from multi-category agents
            query = query.where(
                Agent.id.in_(
                    select(agent_categories.c.agent_id)
                    .join(Category, Category.id == agent_categories.c.category_id)
                    .where(Category.slug == category)
                )
            )

        # Sorting
        sort_column = getattr(Agent, sort_by, Agent.created_at)
        if sort_by in ("downloads", "stars", "rating"):
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(Agent.created_at.desc())

        query = query.options(selectinload(Agent.author)).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_public(self, *, category: str | None = None) -> int:
        """Count public agents with optional category filter."""
        query = select(func.count()).select_from(Agent).where(Agent.is_public.is_(True))

        if category:
            from agent_marketplace_api.models import Category, agent_categories

            query = query.where(
                Agent.id.in_(
                    select(agent_categories.c.agent_id)
                    .join(Category, Category.id == agent_categories.c.category_id)
                    .where(Category.slug == category)
                )
            )

        result = await self.db.execute(query)
        return result.scalar_one()

    async def slug_exists(self, slug: str) -> bool:
        """Check if a slug already exists."""
        result = await self.db.execute(
            select(func.count()).select_from(Agent).where(Agent.slug == slug)
        )
        return result.scalar_one() > 0

    async def increment_downloads(self, agent_id: int) -> None:
        """Increment download counter for an agent."""
        agent = await self.get(agent_id)
        if agent:
            agent.downloads += 1
            await self.db.flush()

    async def increment_stars(self, agent_id: int) -> None:
        """Increment star counter for an agent."""
        agent = await self.get(agent_id)
        if agent:
            agent.stars += 1
            await self.db.flush()

    async def decrement_stars(self, agent_id: int) -> None:
        """Decrement star counter for an agent."""
        agent = await self.get(agent_id)
        if agent and agent.stars > 0:
            agent.stars -= 1
            await self.db.flush()

"""Search service for finding agents and users."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_marketplace_api.models import Agent, User


@dataclass
class AgentSearchResult:
    """Result of agent search."""

    items: list[Agent]
    total: int
    limit: int
    offset: int
    has_more: bool


@dataclass
class GlobalSearchResult:
    """Result of global search."""

    agents: list[Agent]
    users: list[User]
    total: int


class SearchService:
    """Service for searching agents and users."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize search service."""
        self.db = db

    async def search_agents(
        self,
        query: str,
        *,
        category: str | None = None,
        min_rating: float | None = None,
        sort: str = "relevance",
        limit: int = 20,
        offset: int = 0,
    ) -> AgentSearchResult:
        """
        Search agents by name and description.

        Args:
            query: Search query string
            category: Optional category filter
            min_rating: Optional minimum rating filter
            sort: Sort order (relevance, downloads, stars, rating, created_at)
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            AgentSearchResult with matching agents
        """
        search_pattern = f"%{query}%"

        # Build base query
        stmt = (
            select(Agent)
            .where(Agent.is_public.is_(True))
            .where(
                or_(
                    Agent.name.ilike(search_pattern),
                    Agent.description.ilike(search_pattern),
                    Agent.slug.ilike(search_pattern),
                )
            )
        )

        # Apply category filter
        if category:
            stmt = stmt.join(Agent.categories).where(Agent.categories.any(slug=category))

        # Apply rating filter
        if min_rating is not None:
            stmt = stmt.where(Agent.rating >= Decimal(str(min_rating)))

        # Count total before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()

        # Apply sorting
        if sort == "downloads":
            stmt = stmt.order_by(Agent.downloads.desc())
        elif sort == "stars":
            stmt = stmt.order_by(Agent.stars.desc())
        elif sort == "rating":
            stmt = stmt.order_by(Agent.rating.desc())
        elif sort == "created_at":
            stmt = stmt.order_by(Agent.created_at.desc())
        else:  # relevance - prioritize name matches, then by downloads
            stmt = stmt.order_by(Agent.downloads.desc(), Agent.stars.desc())

        # Apply pagination and load relationships
        stmt = stmt.options(selectinload(Agent.author)).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return AgentSearchResult(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(items) < total,
        )

    async def search_users(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> list[User]:
        """
        Search users by username.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching users
        """
        search_pattern = f"%{query}%"

        stmt = (
            select(User)
            .where(User.is_active.is_(True))
            .where(
                or_(
                    User.username.ilike(search_pattern),
                    User.bio.ilike(search_pattern),
                )
            )
            .order_by(User.reputation.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def global_search(
        self,
        query: str,
        *,
        search_type: str | None = None,
        limit: int = 20,
    ) -> GlobalSearchResult:
        """
        Search across agents and users.

        Args:
            query: Search query string
            search_type: Optional filter for "agents" or "users"
            limit: Maximum results per type

        Returns:
            GlobalSearchResult with agents and users
        """
        agents: list[Agent] = []
        users: list[User] = []

        if search_type is None or search_type == "agents":
            agent_result = await self.search_agents(query, limit=limit)
            agents = agent_result.items

        if search_type is None or search_type == "users":
            users = await self.search_users(query, limit=limit)

        total = len(agents) + len(users)

        return GlobalSearchResult(
            agents=agents,
            users=users,
            total=total,
        )

    async def get_suggestions(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[str]:
        """
        Get search suggestions based on partial query.

        Args:
            query: Partial search query
            limit: Maximum suggestions to return

        Returns:
            List of suggestion strings
        """
        search_pattern = f"{query}%"

        # Get agent names that start with the query
        stmt = (
            select(Agent.name)
            .where(Agent.is_public.is_(True))
            .where(Agent.name.ilike(search_pattern))
            .order_by(Agent.downloads.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        suggestions = [row[0] for row in result.all()]

        # If not enough suggestions, try partial matches
        if len(suggestions) < limit:
            partial_pattern = f"%{query}%"
            remaining = limit - len(suggestions)

            stmt = (
                select(Agent.name)
                .where(Agent.is_public.is_(True))
                .where(Agent.name.ilike(partial_pattern))
                .where(~Agent.name.in_(suggestions))
                .order_by(Agent.downloads.desc())
                .limit(remaining)
            )

            result = await self.db.execute(stmt)
            suggestions.extend(row[0] for row in result.all())

        return suggestions


def get_search_service(db: AsyncSession) -> SearchService:
    """Factory function to create SearchService."""
    return SearchService(db)

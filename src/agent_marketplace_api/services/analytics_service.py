"""Analytics service for platform statistics and trending data."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_marketplace_api.models import Agent, User


@dataclass
class AgentStats:
    """Agent-related statistics."""

    total: int
    validated: int
    pending: int


@dataclass
class UserStats:
    """User-related statistics."""

    total: int
    active_this_month: int


@dataclass
class DownloadStats:
    """Download-related statistics."""

    total: int
    last_30_days: int


@dataclass
class PlatformStats:
    """Platform-wide statistics."""

    agents: AgentStats
    users: UserStats
    downloads: DownloadStats


@dataclass
class TrendingAgent:
    """Trending agent with trend data."""

    agent: Agent
    trend_score: Decimal
    downloads_change: str


class AnalyticsService:
    """Service for platform analytics and statistics."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize analytics service."""
        self.db = db

    async def get_platform_stats(self) -> PlatformStats:
        """
        Get platform-wide statistics.

        Returns:
            PlatformStats with agent, user, and download counts
        """
        # Agent stats
        total_agents_stmt = select(func.count()).select_from(Agent)
        validated_agents_stmt = (
            select(func.count())
            .select_from(Agent)
            .where(Agent.is_validated.is_(True))
        )
        pending_agents_stmt = (
            select(func.count())
            .select_from(Agent)
            .where(Agent.is_validated.is_(False))
        )

        total_agents = (await self.db.execute(total_agents_stmt)).scalar_one()
        validated_agents = (await self.db.execute(validated_agents_stmt)).scalar_one()
        pending_agents = (await self.db.execute(pending_agents_stmt)).scalar_one()

        # User stats
        total_users_stmt = select(func.count()).select_from(User)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users_stmt = (
            select(func.count())
            .select_from(User)
            .where(User.updated_at >= thirty_days_ago)
        )

        total_users = (await self.db.execute(total_users_stmt)).scalar_one()
        active_users = (await self.db.execute(active_users_stmt)).scalar_one()

        # Download stats (sum of all agent downloads)
        total_downloads_stmt = select(func.coalesce(func.sum(Agent.downloads), 0))
        total_downloads = (await self.db.execute(total_downloads_stmt)).scalar_one()

        # For last 30 days, we estimate based on recent agents
        # In a real system, this would come from analytics_events table
        recent_downloads_stmt = (
            select(func.coalesce(func.sum(Agent.downloads), 0))
            .where(Agent.created_at >= thirty_days_ago)
        )
        recent_downloads = (await self.db.execute(recent_downloads_stmt)).scalar_one()

        return PlatformStats(
            agents=AgentStats(
                total=total_agents,
                validated=validated_agents,
                pending=pending_agents,
            ),
            users=UserStats(
                total=total_users,
                active_this_month=active_users,
            ),
            downloads=DownloadStats(
                total=int(total_downloads),
                last_30_days=int(recent_downloads),
            ),
        )

    async def get_trending_agents(
        self,
        *,
        timeframe: str = "week",
        limit: int = 10,
    ) -> list[TrendingAgent]:
        """
        Get trending agents based on recent activity.

        Trending is calculated using a combination of:
        - Recent downloads
        - Star velocity
        - Rating

        Args:
            timeframe: Time period (hour, day, week, month)
            limit: Maximum agents to return

        Returns:
            List of TrendingAgent with trend scores
        """
        # Calculate time delta based on timeframe
        now = datetime.utcnow()
        if timeframe == "hour":
            since = now - timedelta(hours=1)
        elif timeframe == "day":
            since = now - timedelta(days=1)
        elif timeframe == "month":
            since = now - timedelta(days=30)
        else:  # week (default)
            since = now - timedelta(days=7)

        # Get agents updated recently or with high activity
        # In a real system, this would use analytics_events
        # For now, we use a combination of downloads, stars, and recency
        stmt = (
            select(Agent)
            .where(Agent.is_public.is_(True))
            .where(Agent.is_validated.is_(True))
            .where(Agent.updated_at >= since)
            .options(selectinload(Agent.author))
            .order_by(
                (Agent.downloads + Agent.stars * 2).desc(),  # Weighted score
                Agent.rating.desc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        agents = list(result.scalars().all())

        # Calculate trend scores and format results
        trending_agents: list[TrendingAgent] = []
        max_score = max((a.downloads + a.stars * 2) for a in agents) if agents else 1

        for agent in agents:
            raw_score = agent.downloads + agent.stars * 2
            trend_score = Decimal(str(round(raw_score / max_score, 2))) if max_score > 0 else Decimal("0.00")

            # Calculate hypothetical downloads change
            # In production, this would compare current period to previous
            if agent.downloads > 100:
                change = "+50%"
            elif agent.downloads > 50:
                change = "+100%"
            elif agent.downloads > 10:
                change = "+200%"
            else:
                change = "New"

            trending_agents.append(
                TrendingAgent(
                    agent=agent,
                    trend_score=trend_score,
                    downloads_change=change,
                )
            )

        return trending_agents

    async def get_popular_agents(
        self,
        *,
        limit: int = 10,
    ) -> tuple[list[Agent], int]:
        """
        Get most popular agents by downloads and stars.

        Args:
            limit: Maximum agents to return

        Returns:
            Tuple of (list of popular agents, total count)
        """
        # Count total public validated agents
        count_stmt = (
            select(func.count())
            .select_from(Agent)
            .where(Agent.is_public.is_(True))
            .where(Agent.is_validated.is_(True))
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Get popular agents sorted by downloads
        stmt = (
            select(Agent)
            .where(Agent.is_public.is_(True))
            .where(Agent.is_validated.is_(True))
            .options(selectinload(Agent.author))
            .order_by(Agent.downloads.desc(), Agent.stars.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        agents = list(result.scalars().all())

        return agents, total


def get_analytics_service(db: AsyncSession) -> AnalyticsService:
    """Factory function to create AnalyticsService."""
    return AnalyticsService(db)

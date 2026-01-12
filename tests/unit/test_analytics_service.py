"""Unit tests for analytics service."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import Agent, User
from agent_marketplace_api.services.analytics_service import (
    AnalyticsService,
    get_analytics_service,
)


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        github_id=70001,
        username="analyticsuser",
        email="analyticsuser@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create an inactive user (not updated recently)."""
    user = User(
        github_id=70002,
        username="inactiveuser",
        email="inactive@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    # Manually set updated_at to 60 days ago
    user.updated_at = datetime.utcnow() - timedelta(days=60)
    await db_session.flush()
    return user


@pytest.fixture
async def test_agents(db_session: AsyncSession, test_user: User) -> list[Agent]:
    """Create test agents with various stats."""
    agents = [
        Agent(
            name="Popular Agent",
            slug="popular-agent",
            description="A very popular agent",
            author_id=test_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=True,
            downloads=500,
            stars=200,
        ),
        Agent(
            name="New Agent",
            slug="new-agent",
            description="A newly created agent",
            author_id=test_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=True,
            downloads=50,
            stars=20,
        ),
        Agent(
            name="Pending Agent",
            slug="pending-agent",
            description="An agent pending validation",
            author_id=test_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=False,
            downloads=10,
            stars=5,
        ),
        Agent(
            name="Private Agent",
            slug="private-analytics-agent",
            description="A private agent",
            author_id=test_user.id,
            current_version="1.0.0",
            is_public=False,
            is_validated=True,
            downloads=25,
            stars=10,
        ),
    ]
    for agent in agents:
        db_session.add(agent)
    await db_session.flush()
    return agents


class TestGetPlatformStats:
    """Tests for get_platform_stats method."""

    @pytest.mark.asyncio
    async def test_returns_agent_counts(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test platform stats returns correct agent counts."""
        service = AnalyticsService(db_session)
        stats = await service.get_platform_stats()

        assert stats.agents.total >= 4
        assert stats.agents.validated >= 3  # 3 validated (one is pending)
        assert stats.agents.pending >= 1  # 1 pending

    @pytest.mark.asyncio
    async def test_returns_user_counts(
        self,
        db_session: AsyncSession,
        test_user: User,  # noqa: ARG002
        inactive_user: User,  # noqa: ARG002
    ) -> None:
        """Test platform stats returns correct user counts."""
        service = AnalyticsService(db_session)
        stats = await service.get_platform_stats()

        assert stats.users.total >= 2
        # Active user count depends on updated_at being within 30 days
        assert stats.users.active_this_month >= 1

    @pytest.mark.asyncio
    async def test_returns_download_stats(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test platform stats returns download statistics."""
        service = AnalyticsService(db_session)
        stats = await service.get_platform_stats()

        # Total downloads should sum all agent downloads
        assert stats.downloads.total >= 500 + 50 + 10 + 25


class TestGetTrendingAgents:
    """Tests for get_trending_agents method."""

    @pytest.mark.asyncio
    async def test_returns_trending_agents(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test trending returns validated public agents."""
        service = AnalyticsService(db_session)
        trending = await service.get_trending_agents()

        # All trending agents should be public and validated
        for item in trending:
            assert item.agent.is_public
            assert item.agent.is_validated

    @pytest.mark.asyncio
    async def test_trending_has_trend_data(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test trending agents include trend score and change."""
        service = AnalyticsService(db_session)
        trending = await service.get_trending_agents()

        for item in trending:
            assert item.trend_score is not None
            assert item.downloads_change is not None

    @pytest.mark.asyncio
    async def test_trending_respects_limit(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test trending respects limit parameter."""
        service = AnalyticsService(db_session)
        trending = await service.get_trending_agents(limit=1)

        assert len(trending) <= 1

    @pytest.mark.asyncio
    async def test_trending_timeframes(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test trending with different timeframes."""
        service = AnalyticsService(db_session)

        for timeframe in ["hour", "day", "week", "month"]:
            trending = await service.get_trending_agents(timeframe=timeframe)
            # Should not raise and return a list
            assert isinstance(trending, list)


class TestGetPopularAgents:
    """Tests for get_popular_agents method."""

    @pytest.mark.asyncio
    async def test_returns_popular_agents(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test popular returns validated public agents."""
        service = AnalyticsService(db_session)
        agents, total = await service.get_popular_agents()

        # All popular agents should be public and validated
        for agent in agents:
            assert agent.is_public
            assert agent.is_validated

        assert total >= 2  # At least 2 validated public agents

    @pytest.mark.asyncio
    async def test_popular_sorted_by_downloads(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test popular agents are sorted by downloads."""
        service = AnalyticsService(db_session)
        agents, _ = await service.get_popular_agents()

        if len(agents) > 1:
            downloads = [a.downloads for a in agents]
            assert downloads == sorted(downloads, reverse=True)

    @pytest.mark.asyncio
    async def test_popular_respects_limit(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test popular respects limit parameter."""
        service = AnalyticsService(db_session)
        agents, _ = await service.get_popular_agents(limit=1)

        assert len(agents) <= 1


class TestGetAnalyticsServiceFactory:
    """Tests for get_analytics_service factory."""

    def test_factory_creates_service(self) -> None:
        """Test factory creates AnalyticsService."""
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = get_analytics_service(mock_db)

        assert isinstance(service, AnalyticsService)

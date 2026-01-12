"""Integration tests for search and analytics API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import User
from agent_marketplace_api.models.agent import Agent


@pytest.fixture
async def search_user(db_session: AsyncSession) -> User:
    """Create a user for search tests."""
    user = User(
        github_id=80001,
        username="searchapiuser",
        email="searchapi@example.com",
        bio="Expert agent developer",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def search_agents(db_session: AsyncSession, search_user: User) -> list[Agent]:
    """Create agents for search tests."""
    agents = [
        Agent(
            name="Code Analysis Tool",
            slug="code-analysis-tool",
            description="Analyzes code quality and patterns",
            author_id=search_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=True,
            downloads=150,
            stars=75,
        ),
        Agent(
            name="Test Generator",
            slug="test-generator",
            description="Automatically generates unit tests",
            author_id=search_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=True,
            downloads=200,
            stars=100,
        ),
        Agent(
            name="Documentation Helper",
            slug="documentation-helper",
            description="Helps write documentation for code",
            author_id=search_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=True,
            downloads=100,
            stars=50,
        ),
        Agent(
            name="Pending Code Agent",
            slug="pending-code-agent",
            description="A code agent pending validation",
            author_id=search_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=False,
            downloads=10,
            stars=5,
        ),
    ]
    for agent in agents:
        db_session.add(agent)
    await db_session.flush()
    for agent in agents:
        await db_session.refresh(agent)
    return agents


class TestGlobalSearch:
    """Tests for GET /api/v1/search endpoint."""

    @pytest.mark.asyncio
    async def test_global_search_success(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
        search_user: User,  # noqa: ARG002
    ) -> None:
        """Test global search returns agents and users."""
        response = await client.get("/api/v1/search?q=code")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "users" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_global_search_agents_only(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test global search with type filter for agents."""
        response = await client.get("/api/v1/search?q=code&type=agents")

        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 0

    @pytest.mark.asyncio
    async def test_global_search_users_only(
        self,
        client: AsyncClient,
        search_user: User,  # noqa: ARG002
    ) -> None:
        """Test global search with type filter for users."""
        response = await client.get("/api/v1/search?q=searchapiuser&type=users")

        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 0

    @pytest.mark.asyncio
    async def test_global_search_empty_query(
        self,
        client: AsyncClient,
    ) -> None:
        """Test global search with empty query returns 422."""
        response = await client.get("/api/v1/search?q=")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_global_search_with_limit(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test global search respects limit parameter."""
        response = await client.get("/api/v1/search?q=code&limit=1")

        assert response.status_code == 200


class TestAgentSearch:
    """Tests for GET /api/v1/search/agents endpoint."""

    @pytest.mark.asyncio
    async def test_agent_search_success(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test agent search returns matching agents."""
        response = await client.get("/api/v1/search/agents?q=code")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "has_more" in data

    @pytest.mark.asyncio
    async def test_agent_search_by_description(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test agent search matches description."""
        response = await client.get("/api/v1/search/agents?q=generates")

        assert response.status_code == 200
        # Should find "Test Generator" by description
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_agent_search_sort_downloads(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test agent search sorted by downloads."""
        response = await client.get("/api/v1/search/agents?q=code&sort=downloads")

        assert response.status_code == 200
        data = response.json()
        if len(data["items"]) > 1:
            downloads = [item["downloads"] for item in data["items"]]
            assert downloads == sorted(downloads, reverse=True)

    @pytest.mark.asyncio
    async def test_agent_search_sort_stars(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test agent search sorted by stars."""
        response = await client.get("/api/v1/search/agents?q=code&sort=stars")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_agent_search_sort_rating(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test agent search sorted by rating."""
        response = await client.get("/api/v1/search/agents?q=code&sort=rating")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_agent_search_sort_created_at(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test agent search sorted by creation date."""
        response = await client.get("/api/v1/search/agents?q=code&sort=created_at")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_agent_search_pagination(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test agent search with pagination."""
        response = await client.get("/api/v1/search/agents?q=code&limit=1&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 1


class TestSearchSuggestions:
    """Tests for GET /api/v1/search/suggestions endpoint."""

    @pytest.mark.asyncio
    async def test_suggestions_success(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test suggestions returns matching agent names."""
        response = await client.get("/api/v1/search/suggestions?q=Code")

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)

    @pytest.mark.asyncio
    async def test_suggestions_partial_match(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test suggestions with partial query."""
        response = await client.get("/api/v1/search/suggestions?q=Test")

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data

    @pytest.mark.asyncio
    async def test_suggestions_empty_query(
        self,
        client: AsyncClient,
    ) -> None:
        """Test suggestions with empty query returns 422."""
        response = await client.get("/api/v1/search/suggestions?q=")

        assert response.status_code == 422


class TestPlatformStats:
    """Tests for GET /api/v1/stats endpoint."""

    @pytest.mark.asyncio
    async def test_stats_success(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
        search_user: User,  # noqa: ARG002
    ) -> None:
        """Test platform stats returns all categories."""
        response = await client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "users" in data
        assert "downloads" in data

    @pytest.mark.asyncio
    async def test_stats_agent_counts(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test platform stats has correct structure for agents."""
        response = await client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data["agents"]
        assert "validated" in data["agents"]
        assert "pending" in data["agents"]

    @pytest.mark.asyncio
    async def test_stats_user_counts(
        self,
        client: AsyncClient,
        search_user: User,  # noqa: ARG002
    ) -> None:
        """Test platform stats has correct structure for users."""
        response = await client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data["users"]
        assert "active_this_month" in data["users"]

    @pytest.mark.asyncio
    async def test_stats_download_counts(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test platform stats has correct structure for downloads."""
        response = await client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data["downloads"]
        assert "last_30_days" in data["downloads"]


class TestTrendingAgents:
    """Tests for GET /api/v1/trending endpoint."""

    @pytest.mark.asyncio
    async def test_trending_success(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test trending returns agents list."""
        response = await client.get("/api/v1/trending")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data

    @pytest.mark.asyncio
    async def test_trending_with_timeframe(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test trending with different timeframes."""
        for timeframe in ["hour", "day", "week", "month"]:
            response = await client.get(f"/api/v1/trending?timeframe={timeframe}")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_trending_invalid_timeframe(
        self,
        client: AsyncClient,
    ) -> None:
        """Test trending with invalid timeframe returns 422."""
        response = await client.get("/api/v1/trending?timeframe=invalid")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_trending_with_limit(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test trending respects limit parameter."""
        response = await client.get("/api/v1/trending?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) <= 1

    @pytest.mark.asyncio
    async def test_trending_agent_structure(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test trending agent items have correct structure."""
        response = await client.get("/api/v1/trending")

        assert response.status_code == 200
        data = response.json()
        if data["agents"]:
            item = data["agents"][0]
            assert "agent" in item
            assert "trend_score" in item
            assert "downloads_change" in item


class TestPopularAgents:
    """Tests for GET /api/v1/popular endpoint."""

    @pytest.mark.asyncio
    async def test_popular_success(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test popular returns agents list."""
        response = await client.get("/api/v1/popular")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data

    @pytest.mark.asyncio
    async def test_popular_sorted_by_downloads(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test popular agents are sorted by downloads."""
        response = await client.get("/api/v1/popular")

        assert response.status_code == 200
        data = response.json()
        if len(data["items"]) > 1:
            downloads = [item["downloads"] for item in data["items"]]
            assert downloads == sorted(downloads, reverse=True)

    @pytest.mark.asyncio
    async def test_popular_with_limit(
        self,
        client: AsyncClient,
        search_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test popular respects limit parameter."""
        response = await client.get("/api/v1/popular?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 1

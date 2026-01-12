"""Integration tests for agent API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import Agent, AgentVersion, User


@pytest.fixture
async def author(db_session: AsyncSession) -> User:
    """Create test author."""
    user = User(github_id=123, username="author", email="author@example.com")
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def agent_with_version(db_session: AsyncSession, author: User) -> Agent:
    """Create test agent with version."""
    agent = Agent(
        name="Test Agent",
        slug="test-agent",
        description="A test agent for integration testing",
        author_id=author.id,
        current_version="1.0.0",
        is_public=True,
    )
    db_session.add(agent)
    await db_session.flush()

    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        storage_key="agents/test-agent/1.0.0.zip",
    )
    db_session.add(version)
    await db_session.commit()

    return agent


@pytest.mark.integration
class TestListAgents:
    """Integration tests for GET /api/v1/agents."""

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, client: AsyncClient) -> None:
        """Test listing agents when none exist."""
        response = await client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_agents_with_data(
        self, client: AsyncClient, agent_with_version: Agent  # noqa: ARG002
    ) -> None:
        """Test listing agents returns data."""
        response = await client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["slug"] == "test-agent"
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_agents_pagination(
        self, client: AsyncClient, db_session: AsyncSession, author: User
    ) -> None:
        """Test agent listing with pagination."""
        # Create multiple agents
        for i in range(5):
            agent = Agent(
                name=f"Agent {i}",
                slug=f"agent-{i}",
                description="Test agent",
                author_id=author.id,
                current_version="1.0.0",
            )
            db_session.add(agent)
        await db_session.commit()

        response = await client.get("/api/v1/agents?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["has_more"] is True

    @pytest.mark.asyncio
    async def test_list_agents_pagination_offset(
        self, client: AsyncClient, db_session: AsyncSession, author: User
    ) -> None:
        """Test agent listing with offset."""
        for i in range(5):
            agent = Agent(
                name=f"Agent {i}",
                slug=f"agent-offset-{i}",
                description="Test agent",
                author_id=author.id,
                current_version="1.0.0",
            )
            db_session.add(agent)
        await db_session.commit()

        response = await client.get("/api/v1/agents?limit=2&offset=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["offset"] == 3

    @pytest.mark.asyncio
    async def test_list_agents_limit_validation(self, client: AsyncClient) -> None:
        """Test limit parameter validation."""
        response = await client.get("/api/v1/agents?limit=0")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_agents_sorting(
        self, client: AsyncClient, db_session: AsyncSession, author: User
    ) -> None:
        """Test agent listing with sorting."""
        for i, downloads in enumerate([10, 50, 30]):
            agent = Agent(
                name=f"Agent {i}",
                slug=f"sort-agent-{i}",
                description="Test agent",
                author_id=author.id,
                current_version="1.0.0",
                downloads=downloads,
            )
            db_session.add(agent)
        await db_session.commit()

        response = await client.get("/api/v1/agents?sort=downloads")

        assert response.status_code == 200
        data = response.json()
        # Should be sorted by downloads descending
        assert data["items"][0]["downloads"] == 50


@pytest.mark.integration
class TestGetAgent:
    """Integration tests for GET /api/v1/agents/{slug}."""

    @pytest.mark.asyncio
    async def test_get_agent_success(
        self, client: AsyncClient, agent_with_version: Agent  # noqa: ARG002
    ) -> None:
        """Test getting agent by slug."""
        response = await client.get("/api/v1/agents/test-agent")

        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "test-agent"
        assert data["name"] == "Test Agent"
        assert "author" in data
        assert "versions" in data

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, client: AsyncClient) -> None:
        """Test getting non-existent agent returns 404."""
        response = await client.get("/api/v1/agents/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_agent_includes_versions(
        self, client: AsyncClient, agent_with_version: Agent  # noqa: ARG002
    ) -> None:
        """Test agent response includes version history."""
        response = await client.get("/api/v1/agents/test-agent")

        assert response.status_code == 200
        data = response.json()
        assert len(data["versions"]) == 1
        assert data["versions"][0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_agent_includes_author(
        self, client: AsyncClient, agent_with_version: Agent  # noqa: ARG002
    ) -> None:
        """Test agent response includes author info."""
        response = await client.get("/api/v1/agents/test-agent")

        assert response.status_code == 200
        data = response.json()
        assert data["author"]["username"] == "author"

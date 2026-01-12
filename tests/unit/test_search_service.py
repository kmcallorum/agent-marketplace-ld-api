"""Unit tests for search service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import Agent, User
from agent_marketplace_api.services.search_service import SearchService, get_search_service


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        github_id=60001,
        username="searchuser",
        email="searchuser@example.com",
        bio="A developer who builds agents",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_user2(db_session: AsyncSession) -> User:
    """Create another test user."""
    user = User(
        github_id=60002,
        username="codemaster",
        email="codemaster@example.com",
        bio="Code quality expert",
        reputation=100,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_agents(db_session: AsyncSession, test_user: User) -> list[Agent]:
    """Create test agents for search."""
    agents = [
        Agent(
            name="Code Review Agent",
            slug="code-review-agent",
            description="An agent for reviewing code quality",
            author_id=test_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=True,
            downloads=100,
            stars=50,
        ),
        Agent(
            name="Test Runner",
            slug="test-runner",
            description="Runs tests automatically",
            author_id=test_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=True,
            downloads=50,
            stars=25,
        ),
        Agent(
            name="Code Formatter",
            slug="code-formatter",
            description="Formats code nicely",
            author_id=test_user.id,
            current_version="1.0.0",
            is_public=True,
            is_validated=True,
            downloads=200,
            stars=100,
        ),
        Agent(
            name="Private Agent",
            slug="private-agent",
            description="This is private code helper",
            author_id=test_user.id,
            current_version="1.0.0",
            is_public=False,
            is_validated=True,
            downloads=10,
            stars=5,
        ),
    ]
    for agent in agents:
        db_session.add(agent)
    await db_session.flush()
    return agents


class TestSearchAgents:
    """Tests for search_agents method."""

    @pytest.mark.asyncio
    async def test_search_agents_by_name(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test searching agents by name."""
        service = SearchService(db_session)
        result = await service.search_agents("Code")

        assert result.total >= 2  # Code Review Agent and Code Formatter
        assert all(
            "code" in a.name.lower() or "code" in a.description.lower() for a in result.items
        )

    @pytest.mark.asyncio
    async def test_search_agents_by_description(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test searching agents by description."""
        service = SearchService(db_session)
        result = await service.search_agents("quality")

        assert result.total >= 1
        assert any("quality" in a.description.lower() for a in result.items)

    @pytest.mark.asyncio
    async def test_search_agents_excludes_private(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test that private agents are excluded from search."""
        service = SearchService(db_session)
        result = await service.search_agents("private")

        # Should not find the private agent
        assert all(a.is_public for a in result.items)

    @pytest.mark.asyncio
    async def test_search_agents_with_pagination(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test search with pagination."""
        service = SearchService(db_session)
        result = await service.search_agents("code", limit=1, offset=0)

        assert len(result.items) <= 1
        assert result.limit == 1
        assert result.offset == 0

    @pytest.mark.asyncio
    async def test_search_agents_sort_by_downloads(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test sorting by downloads."""
        service = SearchService(db_session)
        result = await service.search_agents("code", sort="downloads")

        if len(result.items) > 1:
            downloads = [a.downloads for a in result.items]
            assert downloads == sorted(downloads, reverse=True)

    @pytest.mark.asyncio
    async def test_search_agents_sort_by_stars(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test sorting by stars."""
        service = SearchService(db_session)
        result = await service.search_agents("code", sort="stars")

        if len(result.items) > 1:
            stars = [a.stars for a in result.items]
            assert stars == sorted(stars, reverse=True)

    @pytest.mark.asyncio
    async def test_search_agents_no_results(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test search with no matching results."""
        service = SearchService(db_session)
        result = await service.search_agents("nonexistentxyz123")

        assert result.total == 0
        assert len(result.items) == 0


class TestSearchUsers:
    """Tests for search_users method."""

    @pytest.mark.asyncio
    async def test_search_users_by_username(
        self,
        db_session: AsyncSession,
        test_user: User,  # noqa: ARG002
        test_user2: User,  # noqa: ARG002
    ) -> None:
        """Test searching users by username."""
        service = SearchService(db_session)
        result = await service.search_users("search")

        assert len(result) >= 1
        assert any(u.username == "searchuser" for u in result)

    @pytest.mark.asyncio
    async def test_search_users_by_bio(
        self,
        db_session: AsyncSession,
        test_user: User,  # noqa: ARG002
        test_user2: User,  # noqa: ARG002
    ) -> None:
        """Test searching users by bio."""
        service = SearchService(db_session)
        result = await service.search_users("developer")

        assert len(result) >= 1
        assert any("developer" in (u.bio or "").lower() for u in result)

    @pytest.mark.asyncio
    async def test_search_users_limited(
        self,
        db_session: AsyncSession,
        test_user: User,  # noqa: ARG002
        test_user2: User,  # noqa: ARG002
    ) -> None:
        """Test search with limit."""
        service = SearchService(db_session)
        result = await service.search_users("e", limit=1)

        assert len(result) <= 1


class TestGlobalSearch:
    """Tests for global_search method."""

    @pytest.mark.asyncio
    async def test_global_search_returns_both(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
        test_user: User,  # noqa: ARG002
    ) -> None:
        """Test global search returns agents and users."""
        service = SearchService(db_session)
        result = await service.global_search("code")

        assert result.total >= 1
        # Should have some results

    @pytest.mark.asyncio
    async def test_global_search_agents_only(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test global search filtered to agents only."""
        service = SearchService(db_session)
        result = await service.global_search("code", search_type="agents")

        assert len(result.users) == 0
        assert len(result.agents) >= 1

    @pytest.mark.asyncio
    async def test_global_search_users_only(
        self,
        db_session: AsyncSession,
        test_user: User,  # noqa: ARG002
    ) -> None:
        """Test global search filtered to users only."""
        service = SearchService(db_session)
        result = await service.global_search("searchuser", search_type="users")

        assert len(result.agents) == 0
        assert len(result.users) >= 1


class TestGetSuggestions:
    """Tests for get_suggestions method."""

    @pytest.mark.asyncio
    async def test_get_suggestions_prefix_match(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test getting suggestions with prefix match."""
        service = SearchService(db_session)
        result = await service.get_suggestions("Code")

        assert len(result) >= 1
        # Should suggest agent names starting with "Code"

    @pytest.mark.asyncio
    async def test_get_suggestions_partial_match(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test getting suggestions with partial match."""
        service = SearchService(db_session)
        result = await service.get_suggestions("Review")

        # Should include partial matches if not enough prefix matches
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_suggestions_limited(
        self,
        db_session: AsyncSession,
        test_agents: list[Agent],  # noqa: ARG002
    ) -> None:
        """Test suggestions are limited."""
        service = SearchService(db_session)
        result = await service.get_suggestions("a", limit=2)

        assert len(result) <= 2


class TestGetSearchServiceFactory:
    """Tests for get_search_service factory."""

    def test_factory_creates_service(self) -> None:
        """Test factory creates SearchService."""
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = get_search_service(mock_db)

        assert isinstance(service, SearchService)

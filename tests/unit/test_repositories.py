"""Tests for repository layer."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import Agent, User
from agent_marketplace_api.repositories import AgentRepository, BaseRepository


class TestBaseRepository:
    """Tests for BaseRepository."""

    @pytest.mark.asyncio
    async def test_get_returns_entity(self, db_session: AsyncSession) -> None:
        """Test get returns entity by ID."""
        user = User(github_id=123, username="test", email="test@example.com")
        db_session.add(user)
        await db_session.flush()

        repo = BaseRepository(db_session, User)
        result = await repo.get(user.id)

        assert result is not None
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        """Test get returns None for non-existent ID."""
        repo = BaseRepository(db_session, User)
        result = await repo.get(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, db_session: AsyncSession) -> None:
        """Test get_all returns paginated results."""
        for i in range(5):
            user = User(github_id=100 + i, username=f"user{i}", email=f"user{i}@example.com")
            db_session.add(user)
        await db_session.flush()

        repo = BaseRepository(db_session, User)
        result = await repo.get_all(limit=3, offset=0)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_create_adds_entity(self, db_session: AsyncSession) -> None:
        """Test create adds entity to database."""
        user = User(github_id=123, username="test", email="test@example.com")
        repo = BaseRepository(db_session, User)

        result = await repo.create(user)

        assert result.id is not None

    @pytest.mark.asyncio
    async def test_update_refreshes_entity(self, db_session: AsyncSession) -> None:
        """Test update refreshes entity."""
        user = User(github_id=123, username="test", email="test@example.com")
        db_session.add(user)
        await db_session.flush()

        repo = BaseRepository(db_session, User)
        user.username = "updated"
        result = await repo.update(user)

        assert result.username == "updated"

    @pytest.mark.asyncio
    async def test_delete_removes_entity(self, db_session: AsyncSession) -> None:
        """Test delete removes entity."""
        user = User(github_id=123, username="test", email="test@example.com")
        db_session.add(user)
        await db_session.flush()
        user_id = user.id

        repo = BaseRepository(db_session, User)
        await repo.delete(user)

        result = await repo.get(user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_count_returns_total(self, db_session: AsyncSession) -> None:
        """Test count returns total entities."""
        for i in range(3):
            user = User(github_id=100 + i, username=f"user{i}", email=f"user{i}@example.com")
            db_session.add(user)
        await db_session.flush()

        repo = BaseRepository(db_session, User)
        count = await repo.count()

        assert count == 3


class TestAgentRepository:
    """Tests for AgentRepository."""

    @pytest.fixture
    async def author(self, db_session: AsyncSession) -> User:
        """Create test author."""
        user = User(github_id=123, username="author", email="author@example.com")
        db_session.add(user)
        await db_session.flush()
        return user

    @pytest.fixture
    async def agent(self, db_session: AsyncSession, author: User) -> Agent:
        """Create test agent."""
        agent = Agent(
            name="Test Agent",
            slug="test-agent",
            description="A test agent",
            author_id=author.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.flush()
        return agent

    @pytest.mark.asyncio
    async def test_find_by_slug(
        self, db_session: AsyncSession, agent: Agent  # noqa: ARG002
    ) -> None:
        """Test finding agent by slug."""
        repo = AgentRepository(db_session)
        result = await repo.find_by_slug("test-agent")

        assert result is not None
        assert result.slug == "test-agent"

    @pytest.mark.asyncio
    async def test_find_by_slug_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding non-existent slug returns None."""
        repo = AgentRepository(db_session)
        result = await repo.find_by_slug("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_author(
        self, db_session: AsyncSession, author: User, agent: Agent
    ) -> None:
        """Test finding agents by author."""
        repo = AgentRepository(db_session)
        result = await repo.find_by_author(author.id)

        assert len(result) == 1
        assert result[0].id == agent.id

    @pytest.mark.asyncio
    async def test_list_public(
        self, db_session: AsyncSession, agent: Agent  # noqa: ARG002
    ) -> None:
        """Test listing public agents."""
        repo = AgentRepository(db_session)
        result = await repo.list_public()

        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_list_public_with_sorting(
        self, db_session: AsyncSession, author: User
    ) -> None:
        """Test listing public agents with different sort options."""
        # Create agents with different stats
        for i, downloads in enumerate([10, 50, 30]):
            agent = Agent(
                name=f"Agent {i}",
                slug=f"agent-{i}",
                description="Test agent",
                author_id=author.id,
                current_version="1.0.0",
                downloads=downloads,
            )
            db_session.add(agent)
        await db_session.flush()

        repo = AgentRepository(db_session)
        result = await repo.list_public(sort_by="downloads")

        assert result[0].downloads == 50

    @pytest.mark.asyncio
    async def test_count_public(
        self, db_session: AsyncSession, agent: Agent  # noqa: ARG002
    ) -> None:
        """Test counting public agents."""
        repo = AgentRepository(db_session)
        count = await repo.count_public()

        assert count >= 1

    @pytest.mark.asyncio
    async def test_list_public_with_category(
        self, db_session: AsyncSession, author: User
    ) -> None:
        """Test listing public agents with category filter."""
        from agent_marketplace_api.models import Category

        # Create a category
        category = Category(name="Testing", slug="testing")
        db_session.add(category)
        await db_session.flush()

        # Create agent with category
        agent = Agent(
            name="Categorized Agent",
            slug="categorized-agent",
            description="Test agent",
            author_id=author.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.flush()

        # Link agent to category
        from sqlalchemy import insert

        from agent_marketplace_api.models import agent_categories

        await db_session.execute(
            insert(agent_categories).values(agent_id=agent.id, category_id=category.id)
        )
        await db_session.commit()

        repo = AgentRepository(db_session)
        result = await repo.list_public(category="testing")

        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_count_public_with_category(
        self, db_session: AsyncSession, author: User
    ) -> None:
        """Test counting public agents with category filter."""
        from agent_marketplace_api.models import Category

        # Create a category
        category = Category(name="CountTest", slug="count-test")
        db_session.add(category)
        await db_session.flush()

        # Create agent with category
        agent = Agent(
            name="Count Agent",
            slug="count-agent",
            description="Test agent",
            author_id=author.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.flush()

        # Link agent to category
        from sqlalchemy import insert

        from agent_marketplace_api.models import agent_categories

        await db_session.execute(
            insert(agent_categories).values(agent_id=agent.id, category_id=category.id)
        )
        await db_session.commit()

        repo = AgentRepository(db_session)
        count = await repo.count_public(category="count-test")

        assert count >= 1

    @pytest.mark.asyncio
    async def test_slug_exists_true(
        self, db_session: AsyncSession, agent: Agent  # noqa: ARG002
    ) -> None:
        """Test slug_exists returns True for existing slug."""
        repo = AgentRepository(db_session)
        exists = await repo.slug_exists("test-agent")

        assert exists is True

    @pytest.mark.asyncio
    async def test_slug_exists_false(
        self, db_session: AsyncSession
    ) -> None:
        """Test slug_exists returns False for non-existent slug."""
        repo = AgentRepository(db_session)
        exists = await repo.slug_exists("nonexistent")

        assert exists is False

    @pytest.mark.asyncio
    async def test_increment_downloads(
        self, db_session: AsyncSession, agent: Agent
    ) -> None:
        """Test incrementing download counter."""
        repo = AgentRepository(db_session)
        await repo.increment_downloads(agent.id)

        updated = await repo.get(agent.id)
        assert updated is not None
        assert updated.downloads == 1

    @pytest.mark.asyncio
    async def test_increment_downloads_missing_agent(
        self, db_session: AsyncSession
    ) -> None:
        """Test incrementing downloads for non-existent agent does nothing."""
        repo = AgentRepository(db_session)
        await repo.increment_downloads(99999)  # Should not raise

    @pytest.mark.asyncio
    async def test_increment_stars(
        self, db_session: AsyncSession, agent: Agent
    ) -> None:
        """Test incrementing star counter."""
        repo = AgentRepository(db_session)
        await repo.increment_stars(agent.id)

        updated = await repo.get(agent.id)
        assert updated is not None
        assert updated.stars == 1

    @pytest.mark.asyncio
    async def test_increment_stars_missing_agent(
        self, db_session: AsyncSession
    ) -> None:
        """Test incrementing stars for non-existent agent does nothing."""
        repo = AgentRepository(db_session)
        await repo.increment_stars(99999)  # Should not raise

    @pytest.mark.asyncio
    async def test_decrement_stars(
        self, db_session: AsyncSession, author: User
    ) -> None:
        """Test decrementing star counter."""
        agent = Agent(
            name="Test",
            slug="test-stars",
            description="Test agent",
            author_id=author.id,
            current_version="1.0.0",
            stars=5,
        )
        db_session.add(agent)
        await db_session.flush()

        repo = AgentRepository(db_session)
        await repo.decrement_stars(agent.id)

        updated = await repo.get(agent.id)
        assert updated is not None
        assert updated.stars == 4

    @pytest.mark.asyncio
    async def test_decrement_stars_at_zero(
        self, db_session: AsyncSession, agent: Agent
    ) -> None:
        """Test decrementing stars when already at zero."""
        repo = AgentRepository(db_session)
        await repo.decrement_stars(agent.id)

        updated = await repo.get(agent.id)
        assert updated is not None
        assert updated.stars == 0  # Should not go negative

    @pytest.mark.asyncio
    async def test_decrement_stars_missing_agent(
        self, db_session: AsyncSession
    ) -> None:
        """Test decrementing stars for non-existent agent does nothing."""
        repo = AgentRepository(db_session)
        await repo.decrement_stars(99999)  # Should not raise

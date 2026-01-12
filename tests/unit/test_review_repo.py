"""Unit tests for review repositories."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import User
from agent_marketplace_api.models.agent import Agent
from agent_marketplace_api.models.review import Review
from agent_marketplace_api.repositories.review_repo import ReviewRepository, StarRepository


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        github_id=50001,
        username="repouser",
        email="repouser@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_author(db_session: AsyncSession) -> User:
    """Create a test author."""
    user = User(
        github_id=50002,
        username="repoauthor",
        email="repoauthor@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_agent(db_session: AsyncSession, test_author: User) -> Agent:
    """Create a test agent."""
    agent = Agent(
        name="Repo Test Agent",
        slug="repo-test-agent",
        description="Agent for repo tests",
        author_id=test_author.id,
        current_version="1.0.0",
    )
    db_session.add(agent)
    await db_session.flush()
    return agent


@pytest.fixture
async def test_review(
    db_session: AsyncSession, test_agent: Agent, test_user: User
) -> Review:
    """Create a test review."""
    review = Review(
        agent_id=test_agent.id,
        user_id=test_user.id,
        rating=4,
        comment="Test review",
        helpful_count=5,
    )
    db_session.add(review)
    await db_session.flush()
    return review


class TestReviewRepository:
    """Tests for ReviewRepository."""

    @pytest.mark.asyncio
    async def test_get_reviews_sort_recent(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_review: Review,  # noqa: ARG002
    ) -> None:
        """Test getting reviews sorted by recent."""
        repo = ReviewRepository(db_session)
        reviews = await repo.get_reviews_for_agent(
            test_agent.id, limit=20, offset=0, sort="recent"
        )

        assert len(reviews) == 1
        assert reviews[0].rating == 4

    @pytest.mark.asyncio
    async def test_get_reviews_sort_rating(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_review: Review,  # noqa: ARG002
    ) -> None:
        """Test getting reviews sorted by rating."""
        repo = ReviewRepository(db_session)
        reviews = await repo.get_reviews_for_agent(
            test_agent.id, limit=20, offset=0, sort="rating"
        )

        assert len(reviews) == 1
        assert reviews[0].rating == 4

    @pytest.mark.asyncio
    async def test_get_reviews_sort_helpful(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_review: Review,  # noqa: ARG002
    ) -> None:
        """Test getting reviews sorted by helpful (default)."""
        repo = ReviewRepository(db_session)
        reviews = await repo.get_reviews_for_agent(
            test_agent.id, limit=20, offset=0, sort="helpful"
        )

        assert len(reviews) == 1
        assert reviews[0].helpful_count == 5

    @pytest.mark.asyncio
    async def test_increment_helpful(
        self,
        db_session: AsyncSession,
        test_review: Review,
    ) -> None:
        """Test incrementing helpful count."""
        repo = ReviewRepository(db_session)
        original_count = test_review.helpful_count

        await repo.increment_helpful(test_review.id)
        await db_session.refresh(test_review)

        assert test_review.helpful_count == original_count + 1

    @pytest.mark.asyncio
    async def test_increment_helpful_nonexistent(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test incrementing helpful count for non-existent review."""
        repo = ReviewRepository(db_session)
        # Should not raise, just do nothing
        await repo.increment_helpful(99999)


class TestStarRepository:
    """Tests for StarRepository."""

    @pytest.mark.asyncio
    async def test_add_star(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
    ) -> None:
        """Test adding a star."""
        repo = StarRepository(db_session)
        result = await repo.add_star(test_user.id, test_agent.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_add_star_already_starred(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
    ) -> None:
        """Test adding a star when already starred."""
        repo = StarRepository(db_session)
        await repo.add_star(test_user.id, test_agent.id)
        result = await repo.add_star(test_user.id, test_agent.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_star(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
    ) -> None:
        """Test removing a star."""
        repo = StarRepository(db_session)
        await repo.add_star(test_user.id, test_agent.id)
        result = await repo.remove_star(test_user.id, test_agent.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_star_not_starred(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
    ) -> None:
        """Test removing a star when not starred."""
        repo = StarRepository(db_session)
        result = await repo.remove_star(test_user.id, test_agent.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_starred(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
    ) -> None:
        """Test checking if starred."""
        repo = StarRepository(db_session)

        assert await repo.is_starred(test_user.id, test_agent.id) is False

        await repo.add_star(test_user.id, test_agent.id)

        assert await repo.is_starred(test_user.id, test_agent.id) is True

    @pytest.mark.asyncio
    async def test_count_stars(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
        test_author: User,
    ) -> None:
        """Test counting stars."""
        repo = StarRepository(db_session)
        await repo.add_star(test_user.id, test_agent.id)
        await repo.add_star(test_author.id, test_agent.id)

        count = await repo.count_stars(test_agent.id)

        assert count == 2

    @pytest.mark.asyncio
    async def test_get_starred_agents(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
    ) -> None:
        """Test getting starred agents for a user."""
        repo = StarRepository(db_session)
        await repo.add_star(test_user.id, test_agent.id)

        agents = await repo.get_starred_agents(test_user.id)

        assert len(agents) == 1
        assert agents[0].id == test_agent.id

    @pytest.mark.asyncio
    async def test_get_starred_agents_empty(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test getting starred agents when none starred."""
        repo = StarRepository(db_session)

        agents = await repo.get_starred_agents(test_user.id)

        assert len(agents) == 0

    @pytest.mark.asyncio
    async def test_update_agent_star_count(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
    ) -> None:
        """Test updating agent star count."""
        repo = StarRepository(db_session)
        await repo.add_star(test_user.id, test_agent.id)

        await repo.update_agent_star_count(test_agent.id)
        await db_session.refresh(test_agent)

        assert test_agent.stars == 1

    @pytest.mark.asyncio
    async def test_update_agent_star_count_nonexistent(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test updating star count for non-existent agent."""
        repo = StarRepository(db_session)
        # Should not raise, just do nothing
        await repo.update_agent_star_count(99999)

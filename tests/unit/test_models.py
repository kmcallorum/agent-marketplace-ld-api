"""Tests for SQLAlchemy models."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import (
    Agent,
    AgentVersion,
    Category,
    Review,
    User,
    agent_categories,
    agent_stars,
)


class TestUserModel:
    """Tests for User model."""

    def test_user_tablename(self) -> None:
        """Test User has correct table name."""
        assert User.__tablename__ == "users"

    def test_user_columns(self) -> None:
        """Test User has all required columns."""
        mapper = inspect(User)
        columns = {col.key for col in mapper.columns}

        expected = {
            "id",
            "github_id",
            "username",
            "email",
            "avatar_url",
            "bio",
            "reputation",
            "role",
            "is_active",
            "is_blocked",
            "blocked_reason",
            "created_at",
            "updated_at",
        }
        assert columns == expected

    def test_user_repr(self) -> None:
        """Test User string representation."""
        user = User(id=1, username="testuser", github_id=123, email="test@example.com")
        assert repr(user) == "<User(id=1, username='testuser')>"

    @pytest.mark.asyncio
    async def test_user_create(self, db_session: AsyncSession) -> None:
        """Test creating a user in database."""
        user = User(
            github_id=12345,
            username="testuser",
            email="test@example.com",
        )
        db_session.add(user)
        await db_session.commit()

        assert user.id is not None
        assert user.reputation == 0
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)


class TestAgentModel:
    """Tests for Agent model."""

    def test_agent_tablename(self) -> None:
        """Test Agent has correct table name."""
        assert Agent.__tablename__ == "agents"

    def test_agent_columns(self) -> None:
        """Test Agent has all required columns."""
        mapper = inspect(Agent)
        columns = {col.key for col in mapper.columns}

        expected = {
            "id",
            "name",
            "slug",
            "description",
            "author_id",
            "current_version",
            "downloads",
            "stars",
            "rating",
            "is_public",
            "is_validated",
            "created_at",
            "updated_at",
        }
        assert columns == expected

    def test_agent_repr(self) -> None:
        """Test Agent string representation."""
        agent = Agent(
            id=1,
            slug="test-agent",
            name="Test",
            description="Test",
            current_version="1.0.0",
            author_id=1,
        )
        assert repr(agent) == "<Agent(id=1, slug='test-agent')>"

    @pytest.mark.asyncio
    async def test_agent_create_with_user(self, db_session: AsyncSession) -> None:
        """Test creating an agent with a user."""
        user = User(github_id=123, username="author", email="author@example.com")
        db_session.add(user)
        await db_session.flush()

        agent = Agent(
            name="Test Agent",
            slug="test-agent",
            description="A test agent",
            author_id=user.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.commit()

        assert agent.id is not None
        assert agent.downloads == 0
        assert agent.stars == 0
        assert agent.rating == Decimal("0.00")
        assert agent.is_public is True
        assert agent.is_validated is False


class TestAgentVersionModel:
    """Tests for AgentVersion model."""

    def test_agent_version_tablename(self) -> None:
        """Test AgentVersion has correct table name."""
        assert AgentVersion.__tablename__ == "agent_versions"

    def test_agent_version_repr(self) -> None:
        """Test AgentVersion string representation."""
        version = AgentVersion(id=1, version="1.0.0", agent_id=1, storage_key="key")
        assert repr(version) == "<AgentVersion(id=1, version='1.0.0')>"

    @pytest.mark.asyncio
    async def test_agent_version_create(self, db_session: AsyncSession) -> None:
        """Test creating an agent version."""
        user = User(github_id=123, username="author", email="author@example.com")
        db_session.add(user)
        await db_session.flush()

        agent = Agent(
            name="Test",
            slug="test",
            description="Test agent",
            author_id=user.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.flush()

        version = AgentVersion(
            agent_id=agent.id,
            version="1.0.0",
            storage_key="agents/test/1.0.0.zip",
            size_bytes=1024,
            changelog="Initial release",
        )
        db_session.add(version)
        await db_session.commit()

        assert version.id is not None
        assert version.tested is False
        assert version.security_scan_passed is False


class TestCategoryModel:
    """Tests for Category model."""

    def test_category_tablename(self) -> None:
        """Test Category has correct table name."""
        assert Category.__tablename__ == "categories"

    def test_category_repr(self) -> None:
        """Test Category string representation."""
        category = Category(id=1, name="Testing", slug="testing")
        assert repr(category) == "<Category(id=1, slug='testing')>"

    @pytest.mark.asyncio
    async def test_category_create(self, db_session: AsyncSession) -> None:
        """Test creating a category."""
        category = Category(
            name="Project Management",
            slug="pm",
            icon="clipboard",
            description="Task tracking agents",
        )
        db_session.add(category)
        await db_session.commit()

        assert category.id is not None
        assert category.agent_count == 0


class TestReviewModel:
    """Tests for Review model."""

    def test_review_tablename(self) -> None:
        """Test Review has correct table name."""
        assert Review.__tablename__ == "reviews"

    def test_review_repr(self) -> None:
        """Test Review string representation."""
        review = Review(id=1, agent_id=1, user_id=1, rating=5)
        assert repr(review) == "<Review(id=1, agent_id=1, rating=5)>"

    @pytest.mark.asyncio
    async def test_review_create(self, db_session: AsyncSession) -> None:
        """Test creating a review."""
        user = User(github_id=123, username="reviewer", email="reviewer@example.com")
        db_session.add(user)
        await db_session.flush()

        author = User(github_id=456, username="author", email="author@example.com")
        db_session.add(author)
        await db_session.flush()

        agent = Agent(
            name="Test",
            slug="test",
            description="Test agent",
            author_id=author.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.flush()

        review = Review(
            agent_id=agent.id,
            user_id=user.id,
            rating=5,
            comment="Great agent!",
        )
        db_session.add(review)
        await db_session.commit()

        assert review.id is not None
        assert review.helpful_count == 0


class TestAssociationTables:
    """Tests for association tables."""

    def test_agent_stars_table_exists(self) -> None:
        """Test agent_stars association table exists."""
        assert agent_stars.name == "agent_stars"

    def test_agent_categories_table_exists(self) -> None:
        """Test agent_categories association table exists."""
        assert agent_categories.name == "agent_categories"

    @pytest.mark.asyncio
    async def test_user_star_agent(self, db_session: AsyncSession) -> None:
        """Test user can star an agent via association table."""
        from sqlalchemy import insert, select

        user = User(github_id=123, username="user", email="user@example.com")
        author = User(github_id=456, username="author", email="author@example.com")
        db_session.add_all([user, author])
        await db_session.flush()

        agent = Agent(
            name="Test",
            slug="test",
            description="Test agent",
            author_id=author.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.flush()

        # Star the agent via association table
        await db_session.execute(insert(agent_stars).values(user_id=user.id, agent_id=agent.id))
        await db_session.commit()

        # Verify star exists in association table
        result = await db_session.execute(
            select(agent_stars).where(
                agent_stars.c.user_id == user.id,
                agent_stars.c.agent_id == agent.id,
            )
        )
        assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_agent_category_relationship(self, db_session: AsyncSession) -> None:
        """Test agent-category many-to-many relationship via association table."""
        from sqlalchemy import insert, select

        user = User(github_id=123, username="author", email="author@example.com")
        db_session.add(user)
        await db_session.flush()

        category = Category(name="Testing", slug="testing")
        db_session.add(category)
        await db_session.flush()

        agent = Agent(
            name="Test",
            slug="test",
            description="Test agent",
            author_id=user.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.flush()

        # Link agent to category via association table
        await db_session.execute(
            insert(agent_categories).values(agent_id=agent.id, category_id=category.id)
        )
        await db_session.commit()

        # Verify relationship exists in association table
        result = await db_session.execute(
            select(agent_categories).where(
                agent_categories.c.agent_id == agent.id,
                agent_categories.c.category_id == category.id,
            )
        )
        assert result.fetchone() is not None

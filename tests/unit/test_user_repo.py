"""Unit tests for user repository."""


import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import User
from agent_marketplace_api.repositories.user_repo import UserRepository


@pytest.fixture
def user_repo(db_session: AsyncSession) -> UserRepository:
    """Create a user repository instance."""
    return UserRepository(db_session)


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """Create a sample user in the database."""
    user = User(
        github_id=12345,
        username="testuser",
        email="test@example.com",
        avatar_url="https://example.com/avatar.png",
        bio="Test bio",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


class TestUserRepository:
    """Tests for UserRepository."""

    @pytest.mark.asyncio
    async def test_create_user(
        self,
        user_repo: UserRepository,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test creating a user."""
        user = User(
            github_id=99999,
            username="newuser",
            email="new@example.com",
        )

        created = await user_repo.create(user)

        assert created.id is not None
        assert created.github_id == 99999
        assert created.username == "newuser"
        assert created.email == "new@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self,
        user_repo: UserRepository,
        sample_user: User,
    ) -> None:
        """Test getting user by ID."""
        user = await user_repo.get(sample_user.id)

        assert user is not None
        assert user.id == sample_user.id
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_not_found(
        self,
        user_repo: UserRepository,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test getting non-existent user."""
        user = await user_repo.get(99999)

        assert user is None

    @pytest.mark.asyncio
    async def test_find_by_github_id(
        self,
        user_repo: UserRepository,
        sample_user: User,
    ) -> None:
        """Test finding user by GitHub ID."""
        user = await user_repo.find_by_github_id(sample_user.github_id)

        assert user is not None
        assert user.github_id == sample_user.github_id
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_find_by_github_id_not_found(
        self,
        user_repo: UserRepository,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test finding user by non-existent GitHub ID."""
        user = await user_repo.find_by_github_id(99999)

        assert user is None

    @pytest.mark.asyncio
    async def test_find_by_username(
        self,
        user_repo: UserRepository,
        sample_user: User,
    ) -> None:
        """Test finding user by username."""
        user = await user_repo.find_by_username(sample_user.username)

        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_find_by_username_not_found(
        self,
        user_repo: UserRepository,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test finding user by non-existent username."""
        user = await user_repo.find_by_username("nonexistent")

        assert user is None

    @pytest.mark.asyncio
    async def test_find_by_email(
        self,
        user_repo: UserRepository,
        sample_user: User,
    ) -> None:
        """Test finding user by email."""
        user = await user_repo.find_by_email(sample_user.email)

        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_find_by_email_not_found(
        self,
        user_repo: UserRepository,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test finding user by non-existent email."""
        user = await user_repo.find_by_email("nonexistent@example.com")

        assert user is None

    @pytest.mark.asyncio
    async def test_update_user(
        self,
        user_repo: UserRepository,
        sample_user: User,
    ) -> None:
        """Test updating a user."""
        sample_user.bio = "Updated bio"
        sample_user.avatar_url = "https://new-avatar.com/img.png"

        updated = await user_repo.update(sample_user)

        assert updated.bio == "Updated bio"
        assert updated.avatar_url == "https://new-avatar.com/img.png"

    @pytest.mark.asyncio
    async def test_delete_user(
        self,
        user_repo: UserRepository,
        sample_user: User,
    ) -> None:
        """Test deleting a user."""
        user_id = sample_user.id

        await user_repo.delete(sample_user)

        user = await user_repo.get(user_id)
        assert user is None

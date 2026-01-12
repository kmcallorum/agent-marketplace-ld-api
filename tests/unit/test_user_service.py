"""Unit tests for user service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.auth import GitHubUser
from agent_marketplace_api.models import User
from agent_marketplace_api.repositories.user_repo import UserRepository
from agent_marketplace_api.services.user_service import UserNotFoundError, UserService


@pytest.fixture
def user_repo(db_session: AsyncSession) -> UserRepository:
    """Create a user repository instance."""
    return UserRepository(db_session)


@pytest.fixture
def user_service(user_repo: UserRepository) -> UserService:
    """Create a user service instance."""
    return UserService(user_repo)


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


class TestUserService:
    """Tests for UserService."""

    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self,
        user_service: UserService,
        sample_user: User,
    ) -> None:
        """Test getting user by ID."""
        user = await user_service.get_user_by_id(sample_user.id)

        assert user.id == sample_user.id
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(
        self,
        user_service: UserService,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test getting non-existent user raises error."""
        with pytest.raises(UserNotFoundError, match="User with ID 99999 not found"):
            await user_service.get_user_by_id(99999)


class TestGetOrCreateFromGitHub:
    """Tests for get_or_create_from_github method."""

    @pytest.mark.asyncio
    async def test_create_new_user(
        self,
        user_service: UserService,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test creating a new user from GitHub OAuth."""
        github_user = GitHubUser(
            id=99999,
            login="newgithubuser",
            email="new@github.com",
            avatar_url="https://github.com/avatar.png",
            name="New GitHub User",
        )

        user = await user_service.get_or_create_from_github(github_user)

        assert user.id is not None
        assert user.github_id == 99999
        assert user.username == "newgithubuser"
        assert user.email == "new@github.com"
        assert user.avatar_url == "https://github.com/avatar.png"
        assert user.bio == "New GitHub User"

    @pytest.mark.asyncio
    async def test_create_user_without_email(
        self,
        user_service: UserService,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test creating a user without email uses placeholder."""
        github_user = GitHubUser(
            id=88888,
            login="noemailuser",
            email=None,
            avatar_url=None,
            name=None,
        )

        user = await user_service.get_or_create_from_github(github_user)

        assert user.email == "noemailuser@github.placeholder"
        assert user.avatar_url is None
        assert user.bio is None

    @pytest.mark.asyncio
    async def test_update_existing_user(
        self,
        user_service: UserService,
        sample_user: User,
    ) -> None:
        """Test updating existing user from GitHub OAuth."""
        github_user = GitHubUser(
            id=sample_user.github_id,
            login="updatedusername",
            email="updated@github.com",
            avatar_url="https://new-avatar.github.com",
            name="Updated Name",
        )

        user = await user_service.get_or_create_from_github(github_user)

        assert user.id == sample_user.id
        assert user.username == "updatedusername"
        assert user.email == "updated@github.com"
        assert user.avatar_url == "https://new-avatar.github.com"

    @pytest.mark.asyncio
    async def test_update_existing_user_partial(
        self,
        user_service: UserService,
        sample_user: User,
    ) -> None:
        """Test updating existing user with partial data."""
        original_email = sample_user.email
        original_avatar = sample_user.avatar_url

        github_user = GitHubUser(
            id=sample_user.github_id,
            login="updatedusername",
            email=None,  # No email
            avatar_url=None,  # No avatar
            name=None,
        )

        user = await user_service.get_or_create_from_github(github_user)

        assert user.id == sample_user.id
        assert user.username == "updatedusername"
        # Email and avatar should remain unchanged when GitHub returns None
        assert user.email == original_email
        assert user.avatar_url == original_avatar

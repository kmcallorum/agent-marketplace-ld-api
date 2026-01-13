"""Unit tests for API dependencies."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.api.deps import get_current_user, get_optional_user
from agent_marketplace_api.models import User
from agent_marketplace_api.security import create_access_token
from agent_marketplace_api.services.user_service import UserNotFoundError, UserService


def make_credentials(token: str) -> HTTPAuthorizationCredentials:
    """Create HTTPAuthorizationCredentials from a token string."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


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


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_missing_sub_in_token(
        self,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test that token without sub claim raises HTTPException."""
        # Create token without sub claim
        token = create_access_token({"username": "testuser"})
        credentials = make_credentials(token)

        mock_service = AsyncMock(spec=UserService)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, mock_service)

        assert exc_info.value.status_code == 401
        # The HTTPException for missing sub gets caught by generic handler
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_generic_exception_handler(
        self,
        sample_user: User,
    ) -> None:
        """Test that generic exceptions are caught and converted to HTTPException."""
        token = create_access_token({"sub": str(sample_user.id), "username": sample_user.username})
        credentials = make_credentials(token)

        # Create a mock service that raises an unexpected exception
        mock_service = AsyncMock(spec=UserService)
        mock_service.get_user_by_id.side_effect = ValueError("Unexpected error")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, mock_service)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_user_not_found_raises_generic_exception(
        self,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test that UserNotFoundError is caught by generic exception handler."""
        token = create_access_token({"sub": "99999", "username": "nonexistent"})
        credentials = make_credentials(token)

        mock_service = AsyncMock(spec=UserService)
        mock_service.get_user_by_id.side_effect = UserNotFoundError("User not found")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, mock_service)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail


class TestGetOptionalUser:
    """Tests for get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_no_token_returns_none(
        self,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test that missing token returns None."""
        mock_service = AsyncMock(spec=UserService)

        result = await get_optional_user(None, mock_service)

        assert result is None
        mock_service.get_user_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(
        self,
        sample_user: User,
    ) -> None:
        """Test that valid token returns user."""
        token = create_access_token({"sub": str(sample_user.id), "username": sample_user.username})
        credentials = make_credentials(token)

        mock_service = AsyncMock(spec=UserService)
        mock_service.get_user_by_id.return_value = sample_user

        result = await get_optional_user(credentials, mock_service)

        assert result == sample_user
        mock_service.get_user_by_id.assert_called_once_with(sample_user.id)

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(
        self,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test that invalid token returns None instead of raising."""
        credentials = make_credentials("invalid.token.here")
        mock_service = AsyncMock(spec=UserService)

        result = await get_optional_user(credentials, mock_service)

        assert result is None
        mock_service.get_user_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_expired_token_returns_none(
        self,
        sample_user: User,
    ) -> None:
        """Test that expired token returns None instead of raising."""
        from datetime import timedelta

        token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username},
            expires_delta=timedelta(seconds=-1),
        )
        credentials = make_credentials(token)

        mock_service = AsyncMock(spec=UserService)

        result = await get_optional_user(credentials, mock_service)

        assert result is None
        mock_service.get_user_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_sub_returns_none(
        self,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test that token without sub returns None."""
        token = create_access_token({"username": "testuser"})
        credentials = make_credentials(token)

        mock_service = AsyncMock(spec=UserService)

        result = await get_optional_user(credentials, mock_service)

        assert result is None
        mock_service.get_user_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_not_found_returns_none(
        self,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test that UserNotFoundError returns None instead of raising."""
        token = create_access_token({"sub": "99999", "username": "nonexistent"})
        credentials = make_credentials(token)

        mock_service = AsyncMock(spec=UserService)
        mock_service.get_user_by_id.side_effect = UserNotFoundError("User not found")

        result = await get_optional_user(credentials, mock_service)

        assert result is None

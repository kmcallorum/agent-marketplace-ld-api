"""Unit tests for auth module (GitHub OAuth)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_marketplace_api.auth import (
    GitHubOAuthError,
    GitHubUser,
    exchange_github_code,
    get_github_user,
)


class TestExchangeGitHubCode:
    """Tests for exchange_github_code function."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self) -> None:
        """Test successful code exchange."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test_token"}

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            token = await exchange_github_code("test_code")

        assert token == "test_token"

    @pytest.mark.asyncio
    async def test_exchange_code_http_error(self) -> None:
        """Test code exchange with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(GitHubOAuthError, match="Failed to exchange code"):
                await exchange_github_code("test_code")

    @pytest.mark.asyncio
    async def test_exchange_code_oauth_error(self) -> None:
        """Test code exchange with OAuth error in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": "bad_verification_code",
            "error_description": "The code passed is incorrect",
        }

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(GitHubOAuthError, match="The code passed is incorrect"):
                await exchange_github_code("bad_code")

    @pytest.mark.asyncio
    async def test_exchange_code_oauth_error_without_description(self) -> None:
        """Test code exchange with OAuth error without description."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "access_denied"}

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(GitHubOAuthError, match="access_denied"):
                await exchange_github_code("denied_code")

    @pytest.mark.asyncio
    async def test_exchange_code_no_token(self) -> None:
        """Test code exchange with no access token in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(GitHubOAuthError, match="No access token"):
                await exchange_github_code("test_code")


class TestGetGitHubUser:
    """Tests for get_github_user function."""

    @pytest.mark.asyncio
    async def test_get_user_success_with_email(self) -> None:
        """Test successful user fetch with public email."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "email": "test@example.com",
            "avatar_url": "https://avatars.github.com/u/12345",
            "name": "Test User",
        }

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            user = await get_github_user("test_token")

        assert isinstance(user, GitHubUser)
        assert user.id == 12345
        assert user.login == "testuser"
        assert user.email == "test@example.com"
        assert user.avatar_url == "https://avatars.github.com/u/12345"
        assert user.name == "Test User"

    @pytest.mark.asyncio
    async def test_get_user_success_without_email(self) -> None:
        """Test successful user fetch without public email (fetches from emails endpoint)."""
        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "email": None,
            "avatar_url": "https://avatars.github.com/u/12345",
            "name": "Test User",
        }

        email_response = MagicMock()
        email_response.status_code = 200
        email_response.json.return_value = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [user_response, email_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            user = await get_github_user("test_token")

        assert user.email == "primary@example.com"

    @pytest.mark.asyncio
    async def test_get_user_email_endpoint_fails(self) -> None:
        """Test user fetch when email endpoint fails."""
        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "email": None,
            "avatar_url": None,
            "name": None,
        }

        email_response = MagicMock()
        email_response.status_code = 403

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [user_response, email_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            user = await get_github_user("test_token")

        assert user.email is None

    @pytest.mark.asyncio
    async def test_get_user_no_primary_verified_email(self) -> None:
        """Test user fetch when no primary verified email exists."""
        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json.return_value = {
            "id": 12345,
            "login": "testuser",
            "email": None,
            "avatar_url": None,
            "name": None,
        }

        email_response = MagicMock()
        email_response.status_code = 200
        email_response.json.return_value = [
            {"email": "unverified@example.com", "primary": True, "verified": False},
        ]

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [user_response, email_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            user = await get_github_user("test_token")

        assert user.email is None

    @pytest.mark.asyncio
    async def test_get_user_http_error(self) -> None:
        """Test user fetch with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("agent_marketplace_api.auth.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(GitHubOAuthError, match="Failed to get user info"):
                await get_github_user("invalid_token")


class TestGitHubUser:
    """Tests for GitHubUser dataclass."""

    def test_github_user_creation(self) -> None:
        """Test GitHubUser dataclass creation."""
        user = GitHubUser(
            id=123,
            login="testuser",
            email="test@example.com",
            avatar_url="https://example.com/avatar.png",
            name="Test User",
        )

        assert user.id == 123
        assert user.login == "testuser"
        assert user.email == "test@example.com"
        assert user.avatar_url == "https://example.com/avatar.png"
        assert user.name == "Test User"

    def test_github_user_with_none_values(self) -> None:
        """Test GitHubUser with optional None values."""
        user = GitHubUser(
            id=123,
            login="testuser",
            email=None,
            avatar_url=None,
            name=None,
        )

        assert user.id == 123
        assert user.login == "testuser"
        assert user.email is None
        assert user.avatar_url is None
        assert user.name is None

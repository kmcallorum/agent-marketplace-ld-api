"""Integration tests for authentication flow."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.auth import GitHubUser
from agent_marketplace_api.models import User
from agent_marketplace_api.security import create_access_token, create_refresh_token


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


@pytest.fixture
async def blocked_user(db_session: AsyncSession) -> User:
    """Create a blocked user in the database."""
    user = User(
        github_id=99998,
        username="blockeduser",
        email="blocked@example.com",
        avatar_url="https://example.com/blocked.png",
        bio="Blocked user",
        is_blocked=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


class TestGitHubAuthEndpoint:
    """Tests for POST /api/v1/auth/github endpoint."""

    @pytest.mark.asyncio
    async def test_github_auth_new_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test GitHub auth creates new user and returns tokens."""
        mock_github_user = GitHubUser(
            id=99999,
            login="newgithubuser",
            email="new@github.com",
            avatar_url="https://github.com/avatar.png",
            name="New User",
        )

        with (
            patch(
                "agent_marketplace_api.api.v1.auth.exchange_github_code",
                new_callable=AsyncMock,
                return_value="mock_github_token",
            ),
            patch(
                "agent_marketplace_api.api.v1.auth.get_github_user",
                new_callable=AsyncMock,
                return_value=mock_github_user,
            ),
        ):
            response = await client.post(
                "/api/v1/auth/github",
                json={"code": "valid_oauth_code"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "newgithubuser"
        assert data["user"]["email"] == "new@github.com"

    @pytest.mark.asyncio
    async def test_github_auth_existing_user(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test GitHub auth returns tokens for existing user."""
        mock_github_user = GitHubUser(
            id=sample_user.github_id,
            login=sample_user.username,
            email=sample_user.email,
            avatar_url=sample_user.avatar_url,
            name="Test User",
        )

        with (
            patch(
                "agent_marketplace_api.api.v1.auth.exchange_github_code",
                new_callable=AsyncMock,
                return_value="mock_github_token",
            ),
            patch(
                "agent_marketplace_api.api.v1.auth.get_github_user",
                new_callable=AsyncMock,
                return_value=mock_github_user,
            ),
        ):
            response = await client.post(
                "/api/v1/auth/github",
                json={"code": "valid_oauth_code"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["id"] == sample_user.id
        assert data["user"]["username"] == sample_user.username

    @pytest.mark.asyncio
    async def test_github_auth_invalid_code(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test GitHub auth with invalid code returns error."""
        from agent_marketplace_api.auth import GitHubOAuthError

        with patch(
            "agent_marketplace_api.api.v1.auth.exchange_github_code",
            new_callable=AsyncMock,
            side_effect=GitHubOAuthError("Invalid code"),
        ):
            response = await client.post(
                "/api/v1/auth/github",
                json={"code": "invalid_code"},
            )

        assert response.status_code == 400
        assert "Invalid code" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_github_auth_blocked_user(
        self,
        client: AsyncClient,
        blocked_user: User,
    ) -> None:
        """Test GitHub auth rejects blocked users."""
        mock_github_user = GitHubUser(
            id=blocked_user.github_id,
            login=blocked_user.username,
            email=blocked_user.email,
            avatar_url=blocked_user.avatar_url,
            name="Blocked User",
        )

        with (
            patch(
                "agent_marketplace_api.api.v1.auth.exchange_github_code",
                new_callable=AsyncMock,
                return_value="mock_github_token",
            ),
            patch(
                "agent_marketplace_api.api.v1.auth.get_github_user",
                new_callable=AsyncMock,
                return_value=mock_github_user,
            ),
        ):
            response = await client.post(
                "/api/v1/auth/github",
                json={"code": "valid_oauth_code"},
            )

        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["blocked"] is True
        assert "blocked" in detail["message"].lower()


class TestRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test refreshing access token with valid refresh token."""
        refresh_token = create_refresh_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test refresh endpoint rejects access tokens."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test refresh endpoint rejects invalid tokens."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refresh_with_expired_token(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test refresh endpoint rejects expired tokens."""
        from datetime import timedelta

        expired_token = create_refresh_token(
            {"sub": str(sample_user.id), "username": sample_user.username},
            expires_delta=timedelta(seconds=-1),
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": expired_token},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_refresh_with_nonexistent_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test refresh endpoint rejects token for deleted user."""
        refresh_token = create_refresh_token({"sub": "99999", "username": "deleteduser"})

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 401
        assert "User not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refresh_with_missing_sub(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test refresh endpoint rejects token without sub claim."""
        # Create a token without sub claim
        refresh_token = create_refresh_token({"username": "testuser"})

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 401
        assert "Invalid token payload" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refresh_blocked_user(
        self,
        client: AsyncClient,
        blocked_user: User,
    ) -> None:
        """Test refresh endpoint rejects blocked users."""
        refresh_token = create_refresh_token(
            {"sub": str(blocked_user.id), "username": blocked_user.username}
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["blocked"] is True
        assert "blocked" in detail["message"].lower()


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test logout returns 204 No Content."""
        response = await client.post("/api/v1/auth/logout")

        assert response.status_code == 204
        assert response.content == b""


class TestProtectedAgentsEndpoint:
    """Tests for protected POST /api/v1/agents endpoint."""

    @pytest.mark.asyncio
    async def test_create_agent_authenticated(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test creating agent with valid authentication."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        # Mock storage service
        mock_upload_result = MagicMock()
        mock_upload_result.key = "agents/testuser/Test Agent-1.0.0.zip"
        mock_upload_result.size_bytes = 100

        with patch("agent_marketplace_api.api.v1.agents.get_storage_service") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.upload_file.return_value = mock_upload_result
            mock_get_storage.return_value = mock_storage

            # Create a fake ZIP file
            zip_content = b"PK\x03\x04" + b"\x00" * 96

            response = await client.post(
                "/api/v1/agents",
                data={
                    "name": "Test Agent",
                    "description": "A test agent for testing purposes",
                    "category": "testing",
                    "version": "1.0.0",
                },
                files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["slug"] == "test-agent"
        assert data["validation_status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_agent_unauthenticated(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test creating agent without authentication fails."""
        zip_content = b"PK\x03\x04" + b"\x00" * 96

        response = await client.post(
            "/api/v1/agents",
            data={
                "name": "Test Agent",
                "description": "A test agent for testing purposes",
                "category": "testing",
                "version": "1.0.0",
            },
            files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
        )

        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_agent_invalid_token(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test creating agent with invalid token fails."""
        zip_content = b"PK\x03\x04" + b"\x00" * 96

        response = await client.post(
            "/api/v1/agents",
            data={
                "name": "Test Agent",
                "description": "A test agent for testing purposes",
                "category": "testing",
                "version": "1.0.0",
            },
            files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_agent_expired_token(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test creating agent with expired token fails."""
        from datetime import timedelta

        expired_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username},
            expires_delta=timedelta(seconds=-1),
        )

        zip_content = b"PK\x03\x04" + b"\x00" * 96

        response = await client.post(
            "/api/v1/agents",
            data={
                "name": "Test Agent",
                "description": "A test agent for testing purposes",
                "category": "testing",
                "version": "1.0.0",
            },
            files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_agent_validation_error(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test creating agent with invalid data fails."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        zip_content = b"PK\x03\x04" + b"\x00" * 96

        response = await client.post(
            "/api/v1/agents",
            data={
                "name": "AB",  # Too short
                "description": "Short",  # Too short
                "category": "testing",
                "version": "invalid",  # Invalid format
            },
            files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_agent_generates_unique_slug(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test creating multiple agents with same name generates unique slugs."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        # Mock storage service
        mock_upload_result = MagicMock()
        mock_upload_result.key = "agents/testuser/Duplicate Name-1.0.0.zip"
        mock_upload_result.size_bytes = 100

        zip_content = b"PK\x03\x04" + b"\x00" * 96

        with patch("agent_marketplace_api.api.v1.agents.get_storage_service") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.upload_file.return_value = mock_upload_result
            mock_get_storage.return_value = mock_storage

            # Create first agent
            response1 = await client.post(
                "/api/v1/agents",
                data={
                    "name": "Duplicate Name",
                    "description": "First agent with this name",
                    "category": "testing",
                    "version": "1.0.0",
                },
                files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert response1.status_code == 202
            slug1 = response1.json()["slug"]

            # Create second agent with same name
            response2 = await client.post(
                "/api/v1/agents",
                data={
                    "name": "Duplicate Name",
                    "description": "Second agent with this name",
                    "category": "testing",
                    "version": "1.0.0",
                },
                files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert response2.status_code == 202
            slug2 = response2.json()["slug"]

        assert slug1 != slug2
        assert slug1 == "duplicate-name"
        assert slug2 == "duplicate-name-1"

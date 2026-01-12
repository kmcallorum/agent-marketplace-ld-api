"""Integration tests for file upload and download endpoints."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import Agent, AgentVersion, User
from agent_marketplace_api.security import create_access_token
from agent_marketplace_api.storage import FileNotFoundError as StorageFileNotFoundError


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
async def sample_agent(db_session: AsyncSession, sample_user: User) -> Agent:
    """Create a sample agent with a version."""
    agent = Agent(
        name="Test Agent",
        slug="test-agent",
        description="A test agent for testing",
        author_id=sample_user.id,
        current_version="1.0.0",
    )
    db_session.add(agent)
    await db_session.flush()
    await db_session.refresh(agent)

    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        storage_key=f"agents/{sample_user.username}/test-agent-1.0.0.zip",
    )
    db_session.add(version)
    await db_session.flush()
    await db_session.refresh(agent)

    return agent


class TestCreateAgentWithUpload:
    """Tests for POST /api/v1/agents with file upload."""

    @pytest.mark.asyncio
    async def test_create_agent_with_file(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test creating agent with file upload."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        # Mock storage service
        mock_upload_result = MagicMock()
        mock_upload_result.key = "agents/testuser/New Agent-1.0.0.zip"
        mock_upload_result.size_bytes = 100

        with patch(
            "agent_marketplace_api.api.v1.agents.get_storage_service"
        ) as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.upload_file.return_value = mock_upload_result
            mock_get_storage.return_value = mock_storage

            # Create a fake ZIP file
            zip_content = b"PK\x03\x04" + b"\x00" * 96  # Minimal ZIP header

            response = await client.post(
                "/api/v1/agents",
                data={
                    "name": "New Agent",
                    "description": "A brand new agent for testing",
                    "category": "testing",
                    "version": "1.0.0",
                },
                files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["slug"] == "new-agent"
        assert data["validation_status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_agent_invalid_file_type(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test creating agent with non-ZIP file fails."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        response = await client.post(
            "/api/v1/agents",
            data={
                "name": "New Agent",
                "description": "A brand new agent for testing",
                "category": "testing",
                "version": "1.0.0",
            },
            files={"code": ("agent.txt", BytesIO(b"not a zip"), "text/plain")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 400
        assert "ZIP archive" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_agent_unauthenticated(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test creating agent without auth fails."""
        zip_content = b"PK\x03\x04" + b"\x00" * 96

        response = await client.post(
            "/api/v1/agents",
            data={
                "name": "New Agent",
                "description": "A brand new agent for testing",
                "category": "testing",
                "version": "1.0.0",
            },
            files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_agent_upload_failure(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test creating agent when storage upload fails."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        from agent_marketplace_api.storage import UploadError

        with patch(
            "agent_marketplace_api.api.v1.agents.get_storage_service"
        ) as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.upload_file.side_effect = UploadError("Storage error")
            mock_get_storage.return_value = mock_storage

            zip_content = b"PK\x03\x04" + b"\x00" * 96

            response = await client.post(
                "/api/v1/agents",
                data={
                    "name": "New Agent",
                    "description": "A brand new agent for testing",
                    "category": "testing",
                    "version": "1.0.0",
                },
                files={"code": ("agent.zip", BytesIO(zip_content), "application/zip")},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == 500
        assert "Failed to upload" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_agent_file_too_large(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test creating agent with file exceeding size limit fails."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        # Create content larger than 50MB limit
        # We'll mock the read to return a large size without actually allocating it
        large_content = b"PK\x03\x04" + b"\x00" * (50 * 1024 * 1024 + 100)

        response = await client.post(
            "/api/v1/agents",
            data={
                "name": "Large Agent",
                "description": "An agent with a file too large",
                "category": "testing",
                "version": "1.0.0",
            },
            files={"code": ("large.zip", BytesIO(large_content), "application/zip")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 400
        assert "File size exceeds maximum" in response.json()["detail"]


class TestDownloadLatest:
    """Tests for GET /api/v1/agents/{slug}/download."""

    @pytest.mark.asyncio
    async def test_download_latest_success(
        self,
        client: AsyncClient,
        sample_agent: Agent,
    ) -> None:
        """Test downloading latest version redirects to presigned URL."""
        with patch(
            "agent_marketplace_api.api.v1.upload.get_storage_service"
        ) as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.generate_presigned_download_url.return_value = (
                "https://s3.example.com/presigned"
            )
            mock_get_storage.return_value = mock_storage

            response = await client.get(
                f"/api/v1/agents/{sample_agent.slug}/download",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert response.headers["location"] == "https://s3.example.com/presigned"

    @pytest.mark.asyncio
    async def test_download_latest_agent_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test downloading non-existent agent returns 404."""
        response = await client.get(
            "/api/v1/agents/nonexistent/download",
            follow_redirects=False,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_latest_no_versions(
        self,
        client: AsyncClient,
        sample_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test downloading agent with no versions returns 404."""
        # Create agent without version
        agent = Agent(
            name="No Version Agent",
            slug="no-version-agent",
            description="Agent without versions",
            author_id=sample_user.id,
            current_version="1.0.0",
        )
        db_session.add(agent)
        await db_session.flush()

        response = await client.get(
            "/api/v1/agents/no-version-agent/download",
            follow_redirects=False,
        )

        assert response.status_code == 404
        assert "No versions available" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_download_latest_file_not_in_storage(
        self,
        client: AsyncClient,
        sample_agent: Agent,
    ) -> None:
        """Test downloading when file missing from storage returns 404."""
        with patch(
            "agent_marketplace_api.api.v1.upload.get_storage_service"
        ) as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.generate_presigned_download_url.side_effect = (
                StorageFileNotFoundError("File not found")
            )
            mock_get_storage.return_value = mock_storage

            response = await client.get(
                f"/api/v1/agents/{sample_agent.slug}/download",
                follow_redirects=False,
            )

        assert response.status_code == 404
        assert "not found in storage" in response.json()["detail"]


class TestDownloadVersion:
    """Tests for GET /api/v1/agents/{slug}/download/{version}."""

    @pytest.mark.asyncio
    async def test_download_specific_version_success(
        self,
        client: AsyncClient,
        sample_agent: Agent,
    ) -> None:
        """Test downloading specific version redirects to presigned URL."""
        with patch(
            "agent_marketplace_api.api.v1.upload.get_storage_service"
        ) as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.generate_presigned_download_url.return_value = (
                "https://s3.example.com/v1.0.0"
            )
            mock_get_storage.return_value = mock_storage

            response = await client.get(
                f"/api/v1/agents/{sample_agent.slug}/download/1.0.0",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert response.headers["location"] == "https://s3.example.com/v1.0.0"

    @pytest.mark.asyncio
    async def test_download_version_not_found(
        self,
        client: AsyncClient,
        sample_agent: Agent,
    ) -> None:
        """Test downloading non-existent version returns 404."""
        response = await client.get(
            f"/api/v1/agents/{sample_agent.slug}/download/9.9.9",
            follow_redirects=False,
        )

        assert response.status_code == 404
        assert "Version 9.9.9 not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_download_version_agent_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
    ) -> None:
        """Test downloading version of non-existent agent returns 404."""
        response = await client.get(
            "/api/v1/agents/nonexistent/download/1.0.0",
            follow_redirects=False,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_version_file_not_in_storage(
        self,
        client: AsyncClient,
        sample_agent: Agent,
    ) -> None:
        """Test downloading specific version when file missing from storage returns 404."""
        with patch(
            "agent_marketplace_api.api.v1.upload.get_storage_service"
        ) as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.generate_presigned_download_url.side_effect = (
                StorageFileNotFoundError("File not found")
            )
            mock_get_storage.return_value = mock_storage

            response = await client.get(
                f"/api/v1/agents/{sample_agent.slug}/download/1.0.0",
                follow_redirects=False,
            )

        assert response.status_code == 404
        assert "not found in storage" in response.json()["detail"]


class TestPresignedUploadUrl:
    """Tests for GET /api/v1/agents/{slug}/presigned-upload."""

    @pytest.mark.asyncio
    async def test_get_presigned_upload_url_success(
        self,
        client: AsyncClient,
        sample_user: User,
        sample_agent: Agent,
    ) -> None:
        """Test getting presigned upload URL for agent owner."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        with patch(
            "agent_marketplace_api.api.v1.upload.get_storage_service"
        ) as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.generate_presigned_upload_url.return_value = (
                "https://s3.example.com/upload"
            )
            mock_get_storage.return_value = mock_storage

            response = await client.get(
                f"/api/v1/agents/{sample_agent.slug}/presigned-upload?version=2.0.0",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["upload_url"] == "https://s3.example.com/upload"
        assert "storage_key" in data
        assert data["expires_in"] == "3600"

    @pytest.mark.asyncio
    async def test_get_presigned_upload_url_not_owner(
        self,
        client: AsyncClient,
        sample_agent: Agent,
        db_session: AsyncSession,
    ) -> None:
        """Test getting presigned upload URL for non-owner fails."""
        # Create another user
        other_user = User(
            github_id=99999,
            username="otheruser",
            email="other@example.com",
        )
        db_session.add(other_user)
        await db_session.flush()

        access_token = create_access_token(
            {"sub": str(other_user.id), "username": other_user.username}
        )

        response = await client.get(
            f"/api/v1/agents/{sample_agent.slug}/presigned-upload?version=2.0.0",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_presigned_upload_url_unauthenticated(
        self,
        client: AsyncClient,
        sample_agent: Agent,
    ) -> None:
        """Test getting presigned upload URL without auth fails."""
        response = await client.get(
            f"/api/v1/agents/{sample_agent.slug}/presigned-upload?version=2.0.0",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_presigned_upload_url_agent_not_found(
        self,
        client: AsyncClient,
        sample_user: User,
    ) -> None:
        """Test getting presigned upload URL for non-existent agent."""
        access_token = create_access_token(
            {"sub": str(sample_user.id), "username": sample_user.username}
        )

        response = await client.get(
            "/api/v1/agents/nonexistent/presigned-upload?version=1.0.0",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 404

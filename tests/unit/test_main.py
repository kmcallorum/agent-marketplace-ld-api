"""Tests for main FastAPI application."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from agent_marketplace_api.main import app, lifespan


class TestLifespan:
    """Tests for application lifespan."""

    @pytest.mark.asyncio
    async def test_lifespan_disposes_engine(self) -> None:
        """Test lifespan disposes engine on shutdown."""
        mock_engine = AsyncMock()

        with patch("agent_marketplace_api.main.async_engine", mock_engine):
            async with lifespan(app):
                pass

            mock_engine.dispose.assert_called_once()


class TestHealthCheck:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client: AsyncClient) -> None:
        """Test health check returns healthy status."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["database"] == "connected"

    @pytest.mark.asyncio
    async def test_health_check_includes_environment(self, client: AsyncClient) -> None:
        """Test health check includes environment info."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "environment" in data

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_database(self, client: AsyncClient) -> None:
        """Test health check returns unhealthy when database is down."""
        with patch(
            "agent_marketplace_api.main.check_database_connection",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "disconnected"


class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_app_info(self, client: AsyncClient) -> None:
        """Test root endpoint returns application info."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["docs"] == "/docs"


class TestOpenAPI:
    """Tests for OpenAPI documentation."""

    @pytest.mark.asyncio
    async def test_openapi_available(self, client: AsyncClient) -> None:
        """Test OpenAPI schema is available."""
        response = await client.get("/api/v1/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data

    @pytest.mark.asyncio
    async def test_docs_available(self, client: AsyncClient) -> None:
        """Test Swagger docs are available."""
        response = await client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_redoc_available(self, client: AsyncClient) -> None:
        """Test ReDoc is available."""
        response = await client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

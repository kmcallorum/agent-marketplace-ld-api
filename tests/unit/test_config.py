"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest

from agent_marketplace_api.config import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = Settings()

        assert settings.app_name == "Agent Marketplace API"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.environment == "development"
        assert settings.api_v1_prefix == "/api/v1"

    def test_database_defaults(self) -> None:
        """Test default database settings."""
        settings = Settings()

        assert "postgresql+asyncpg" in str(settings.database_url)
        assert settings.database_echo is False
        assert settings.database_pool_size == 20
        assert settings.database_max_overflow == 10

    def test_redis_defaults(self) -> None:
        """Test default Redis settings."""
        settings = Settings()

        assert "redis://localhost:6379" in str(settings.redis_url)

    def test_s3_defaults(self) -> None:
        """Test default S3/MinIO settings."""
        settings = Settings()

        assert settings.s3_endpoint == "http://localhost:9000"
        assert settings.s3_bucket == "agent-marketplace"
        assert settings.s3_region == "us-east-1"

    def test_jwt_defaults(self) -> None:
        """Test default JWT settings."""
        settings = Settings()

        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_access_token_expire_minutes == 30
        assert settings.jwt_refresh_token_expire_days == 7

    def test_settings_from_env(self) -> None:
        """Test settings loaded from environment variables."""
        env_vars = {
            "APP_NAME": "Test App",
            "DEBUG": "true",
            "ENVIRONMENT": "production",
            "DATABASE_POOL_SIZE": "50",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()

            assert settings.app_name == "Test App"
            assert settings.debug is True
            assert settings.environment == "production"
            assert settings.database_pool_size == 50

    def test_get_settings_cached(self) -> None:
        """Test get_settings returns cached instance."""
        # Clear the cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_celery_defaults(self) -> None:
        """Test default Celery settings."""
        settings = Settings()

        assert settings.celery_broker_url == "redis://localhost:6379/1"
        assert settings.celery_result_backend == "redis://localhost:6379/2"


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_environment_literal(self) -> None:
        """Test environment only accepts valid values."""
        settings = Settings(environment="staging")
        assert settings.environment == "staging"

    def test_invalid_environment_raises(self) -> None:
        """Test invalid environment raises validation error."""
        with pytest.raises(ValueError):
            Settings(environment="invalid")  # type: ignore[arg-type]

"""Unit tests for Celery tasks."""

from unittest.mock import MagicMock, patch

import pytest

from agent_marketplace_api.tasks.celery import create_celery_app, health_check
from agent_marketplace_api.tasks.validation import cleanup_old_validations


class TestCreateCeleryApp:
    """Tests for Celery app creation."""

    def test_create_app(self) -> None:
        """Test creating Celery app."""
        app = create_celery_app()

        assert app is not None
        assert app.main == "agent_marketplace"

    def test_app_configuration(self) -> None:
        """Test Celery app configuration."""
        app = create_celery_app()

        assert app.conf.task_serializer == "json"
        assert app.conf.result_serializer == "json"
        assert app.conf.timezone == "UTC"
        assert app.conf.enable_utc is True
        assert app.conf.task_acks_late is True
        assert app.conf.result_expires == 3600

    def test_app_routing(self) -> None:
        """Test task routing configuration."""
        app = create_celery_app()

        routes = app.conf.task_routes
        assert "agent_marketplace_api.tasks.validation.*" in routes
        assert routes["agent_marketplace_api.tasks.validation.*"]["queue"] == "validation"

    def test_app_time_limits(self) -> None:
        """Test task time limit configuration."""
        app = create_celery_app()

        assert app.conf.task_soft_time_limit == 600
        assert app.conf.task_time_limit == 900


class TestHealthCheckTask:
    """Tests for health check task."""

    def test_health_check_returns_status(self) -> None:
        """Test health check returns healthy status."""
        result = health_check()

        assert result["status"] == "healthy"
        assert result["worker"] == "celery"


class TestCleanupOldValidations:
    """Tests for cleanup task."""

    def test_cleanup_default_days(self) -> None:
        """Test cleanup with default days."""
        result = cleanup_old_validations()

        assert result["status"] == "completed"
        assert "cleaned_up" in result

    def test_cleanup_custom_days(self) -> None:
        """Test cleanup with custom days."""
        result = cleanup_old_validations(days=7)

        assert result["status"] == "completed"


class TestValidateAgentTask:
    """Tests for validate_agent_task."""

    @pytest.mark.asyncio
    async def test_update_validation_status(self) -> None:
        """Test _update_validation_status helper."""
        from unittest.mock import AsyncMock

        from agent_marketplace_api.tasks.validation import _update_validation_status

        # Mock the database session using AsyncMock for async context manager
        mock_session = MagicMock()

        # Mock version query result
        mock_version = MagicMock()
        mock_version.tested = False
        mock_version.security_scan_passed = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_version

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        # Create async context manager mock
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "agent_marketplace_api.database.async_session_maker", return_value=mock_session_cm
        ):
            await _update_validation_status(1, "running")

        # Version should be updated
        assert mock_version.tested is False
        assert mock_version.security_scan_passed is False

    @pytest.mark.asyncio
    async def test_update_validation_status_failed(self) -> None:
        """Test _update_validation_status for failed status."""
        from unittest.mock import AsyncMock

        from agent_marketplace_api.tasks.validation import _update_validation_status

        mock_session = MagicMock()
        mock_version = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_version

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "agent_marketplace_api.database.async_session_maker", return_value=mock_session_cm
        ):
            await _update_validation_status(1, "failed", "Error message")

        assert mock_version.tested is True
        assert mock_version.security_scan_passed is False

    @pytest.mark.asyncio
    async def test_update_validation_status_version_not_found(self) -> None:
        """Test _update_validation_status when version not found."""
        from unittest.mock import AsyncMock

        from agent_marketplace_api.tasks.validation import _update_validation_status

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "agent_marketplace_api.database.async_session_maker", return_value=mock_session_cm
        ):
            # Should not raise
            await _update_validation_status(999, "running")

    @pytest.mark.asyncio
    async def test_update_validation_results(self) -> None:
        """Test _update_validation_results helper."""
        from unittest.mock import AsyncMock

        from agent_marketplace_api.services.validation_service import (
            ValidationResult,
            ValidationStatus,
        )
        from agent_marketplace_api.tasks.validation import _update_validation_results
        from agent_marketplace_api.validation.quality import QualityResult
        from agent_marketplace_api.validation.scanner import ScanResult

        mock_session = MagicMock()
        mock_version = MagicMock()
        mock_version.agent = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_version

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        validation_result = ValidationResult(
            status=ValidationStatus.PASSED,
            security_result=ScanResult(passed=True),
            quality_result=QualityResult(passed=True, lint_score=90.0),
        )

        with patch(
            "agent_marketplace_api.database.async_session_maker", return_value=mock_session_cm
        ):
            await _update_validation_results(1, validation_result)

        from decimal import Decimal

        assert mock_version.tested is True
        assert mock_version.security_scan_passed is True
        assert mock_version.quality_score == Decimal("0.9")
        assert mock_version.agent.is_validated is True

    @pytest.mark.asyncio
    async def test_update_validation_results_version_not_found(self) -> None:
        """Test _update_validation_results when version not found."""
        from unittest.mock import AsyncMock

        from agent_marketplace_api.services.validation_service import (
            ValidationResult,
            ValidationStatus,
        )
        from agent_marketplace_api.tasks.validation import _update_validation_results

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        validation_result = ValidationResult(status=ValidationStatus.PASSED)

        with patch(
            "agent_marketplace_api.database.async_session_maker", return_value=mock_session_cm
        ):
            # Should not raise
            await _update_validation_results(999, validation_result)

    @pytest.mark.asyncio
    async def test_update_validation_results_no_security(self) -> None:
        """Test _update_validation_results without security result."""
        from unittest.mock import AsyncMock

        from agent_marketplace_api.services.validation_service import (
            ValidationResult,
            ValidationStatus,
        )
        from agent_marketplace_api.tasks.validation import _update_validation_results

        mock_session = MagicMock()
        mock_version = MagicMock()
        mock_version.agent = None  # No parent agent
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_version

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        # No security or quality results
        validation_result = ValidationResult(status=ValidationStatus.PASSED)

        with patch(
            "agent_marketplace_api.database.async_session_maker", return_value=mock_session_cm
        ):
            await _update_validation_results(1, validation_result)

        assert mock_version.tested is True
        assert mock_version.security_scan_passed is True  # Default when no result


class TestRunValidation:
    """Tests for _run_validation helper."""

    @pytest.mark.asyncio
    async def test_run_validation_success(self) -> None:
        """Test _run_validation runs the full pipeline."""
        import zipfile
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import AsyncMock

        from agent_marketplace_api.tasks.validation import _run_validation

        # Create a temporary zip file with test code
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a simple Python file
            code_content = "def hello():\n    return 'hello'\n"

            # Create zip in memory
            zip_path = temp_path / "test_agent.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("main.py", code_content)

            # Mock storage to return our zip bytes
            mock_storage = MagicMock()
            mock_storage.download_file = AsyncMock(return_value=zip_path.read_bytes())

            # Mock session
            mock_session = MagicMock()
            mock_version = MagicMock()
            mock_version.agent = MagicMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_version
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "agent_marketplace_api.storage.get_storage_service", return_value=mock_storage
            ):
                with patch(
                    "agent_marketplace_api.database.async_session_maker",
                    return_value=mock_session_cm,
                ):
                    result = await _run_validation(1, "agents/test.zip")

            assert isinstance(result, dict)
            assert "status" in result
            assert "passed" in result


class TestValidateAgentTaskExecution:
    """Tests for validate_agent_task execution paths."""

    def test_validate_task_run_success(self) -> None:
        """Test validate_agent_task.run() success path."""
        from agent_marketplace_api.tasks.validation import validate_agent_task

        # Mock the _run_validation coroutine
        with patch("agent_marketplace_api.tasks.validation._run_validation") as mock_validation:
            mock_validation.return_value = {"status": "passed", "passed": True}

            # Use task.run() which executes the task synchronously
            result = validate_agent_task.run(1, "agents/test.zip")

            assert result == {"status": "passed", "passed": True}
            mock_validation.assert_called_once_with(1, "agents/test.zip")

    def test_validate_task_run_max_retries_exceeded(self) -> None:
        """Test validate_agent_task handles MaxRetriesExceededError."""
        from celery.exceptions import MaxRetriesExceededError

        from agent_marketplace_api.tasks.validation import validate_agent_task

        # Mock _run_validation to raise MaxRetriesExceededError
        with patch("agent_marketplace_api.tasks.validation._run_validation") as mock_validation:
            mock_validation.side_effect = MaxRetriesExceededError()

            # Mock _update_validation_status
            with patch(
                "agent_marketplace_api.tasks.validation._update_validation_status"
            ) as mock_update:
                mock_update.return_value = None

                with pytest.raises(MaxRetriesExceededError):
                    validate_agent_task.run(1, "agents/test.zip")

                # Verify status was updated to failed
                mock_update.assert_called_once_with(1, "failed", "Max retries exceeded")

    def test_validate_task_run_exception_triggers_retry(self) -> None:
        """Test validate_agent_task retries on exceptions."""
        from celery.exceptions import Retry

        from agent_marketplace_api.tasks.validation import validate_agent_task

        # Mock _run_validation to raise an exception
        with patch("agent_marketplace_api.tasks.validation._run_validation") as mock_validation:
            mock_validation.side_effect = ValueError("Test error")

            # The task should raise Retry (Celery's retry mechanism)
            with pytest.raises((Retry, ValueError)):
                validate_agent_task.run(1, "agents/test.zip")

    def test_validate_task_success_path(self) -> None:
        """Test successful validation task execution via _run_validation."""
        # Test _run_validation directly which is the core logic
        import zipfile
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import AsyncMock

        from agent_marketplace_api.tasks.validation import _run_validation

        async def run_test() -> None:
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                code_content = "def hello():\n    return 'hello'\n"
                zip_path = temp_path / "test_agent.zip"
                with zipfile.ZipFile(zip_path, "w") as zf:
                    zf.writestr("main.py", code_content)

                mock_storage = MagicMock()
                mock_storage.download_file = AsyncMock(return_value=zip_path.read_bytes())

                mock_session = MagicMock()
                mock_version = MagicMock()
                mock_version.agent = MagicMock()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_version
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_session.commit = AsyncMock()

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                with patch(
                    "agent_marketplace_api.storage.get_storage_service", return_value=mock_storage
                ):
                    with patch(
                        "agent_marketplace_api.database.async_session_maker",
                        return_value=mock_session_cm,
                    ):
                        result = await _run_validation(1, "agents/test.zip")

                assert isinstance(result, dict)
                assert "status" in result

        import asyncio

        asyncio.run(run_test())

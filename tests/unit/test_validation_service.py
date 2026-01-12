"""Unit tests for validation service."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent_marketplace_api.services.validation_service import (
    ValidationConfig,
    ValidationResult,
    ValidationService,
    ValidationStatus,
    get_validation_service,
)
from agent_marketplace_api.validation.quality import QualityResult
from agent_marketplace_api.validation.runner import TestResult
from agent_marketplace_api.validation.scanner import ScanResult


class TestValidationStatus:
    """Tests for ValidationStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert ValidationStatus.PENDING.value == "pending"
        assert ValidationStatus.RUNNING.value == "running"
        assert ValidationStatus.PASSED.value == "passed"
        assert ValidationStatus.FAILED.value == "failed"
        assert ValidationStatus.ERROR.value == "error"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_result_passed(self) -> None:
        """Test passed validation result."""
        result = ValidationResult(
            status=ValidationStatus.PASSED,
            security_result=ScanResult(passed=True),
            quality_result=QualityResult(passed=True, lint_score=100.0),
            test_result=TestResult(passed=True),
        )

        assert result.passed is True
        assert result.details["security"] is True
        assert result.details["quality"] is True
        assert result.details["tests"] is True

    def test_result_failed_security(self) -> None:
        """Test failed due to security."""
        result = ValidationResult(
            status=ValidationStatus.FAILED,
            security_result=ScanResult(passed=False),
            quality_result=QualityResult(passed=True, lint_score=100.0),
            test_result=TestResult(passed=True),
        )

        assert result.passed is False
        assert result.details["security"] is False
        assert result.details["quality"] is True

    def test_result_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = ValidationResult(
            status=ValidationStatus.PASSED,
            security_result=ScanResult(passed=True),
            quality_result=QualityResult(passed=True, lint_score=95.0),
            test_result=TestResult(passed=True, total_tests=10, passed_tests=10),
            total_duration_seconds=5.5,
        )

        data = result.to_dict()

        assert data["status"] == "passed"
        assert data["passed"] is True
        assert data["total_duration_seconds"] == 5.5
        assert data["security"]["passed"] is True
        assert data["quality"]["lint_score"] == 95.0
        assert data["tests"]["total"] == 10

    def test_result_to_dict_with_none_results(self) -> None:
        """Test to_dict with None results."""
        result = ValidationResult(
            status=ValidationStatus.ERROR,
            error_message="Something went wrong",
        )

        data = result.to_dict()

        assert data["status"] == "error"
        assert data["error_message"] == "Something went wrong"
        assert data["security"] is None
        assert data["quality"] is None
        assert data["tests"] is None

    def test_result_details_with_none(self) -> None:
        """Test details property with None results."""
        result = ValidationResult(status=ValidationStatus.PENDING)

        assert result.details["security"] is False
        assert result.details["quality"] is False
        assert result.details["tests"] is False


class TestValidationConfig:
    """Tests for ValidationConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ValidationConfig()

        assert config.security_severity_threshold == "medium"
        assert config.security_timeout == 300
        assert config.max_lint_issues == 10
        assert config.require_type_hints is False
        assert config.quality_timeout == 300
        assert config.require_tests is False
        assert config.min_coverage is None
        assert config.test_timeout == 600
        assert config.skip_security is False
        assert config.skip_quality is False
        assert config.skip_tests is False

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = ValidationConfig(
            security_severity_threshold="high",
            max_lint_issues=5,
            require_tests=True,
            min_coverage=80.0,
            skip_quality=True,
        )

        assert config.security_severity_threshold == "high"
        assert config.max_lint_issues == 5
        assert config.require_tests is True
        assert config.min_coverage == 80.0
        assert config.skip_quality is True


class TestValidationService:
    """Tests for ValidationService."""

    def test_service_initialization_default(self) -> None:
        """Test service initialization with default config."""
        service = ValidationService()

        assert service.config is not None
        assert service._scanner is not None
        assert service._quality_checker is not None
        assert service._test_runner is not None

    def test_service_initialization_custom_config(self) -> None:
        """Test service initialization with custom config."""
        config = ValidationConfig(
            security_severity_threshold="high",
            max_lint_issues=5,
        )
        service = ValidationService(config)

        assert service.config.security_severity_threshold == "high"
        assert service.config.max_lint_issues == 5

    @pytest.mark.asyncio
    async def test_validate_all_pass(self) -> None:
        """Test validation when all checks pass."""
        config = ValidationConfig()
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "clean.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                with patch.object(service._quality_checker, "check", new_callable=AsyncMock) as mock_check:
                    with patch.object(service._test_runner, "run", new_callable=AsyncMock) as mock_run:
                        mock_scan.return_value = ScanResult(passed=True)
                        mock_check.return_value = QualityResult(passed=True, lint_score=100.0)
                        mock_run.return_value = TestResult(passed=True)

                        result = await service.validate(Path(temp_dir))

        assert result.status == ValidationStatus.PASSED
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_security_fail(self) -> None:
        """Test validation when security fails."""
        config = ValidationConfig()
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "insecure.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                with patch.object(service._quality_checker, "check", new_callable=AsyncMock) as mock_check:
                    with patch.object(service._test_runner, "run", new_callable=AsyncMock) as mock_run:
                        mock_scan.return_value = ScanResult(passed=False)
                        mock_check.return_value = QualityResult(passed=True, lint_score=100.0)
                        mock_run.return_value = TestResult(passed=True)

                        result = await service.validate(Path(temp_dir))

        assert result.status == ValidationStatus.FAILED
        assert result.passed is False
        assert result.security_result is not None
        assert result.security_result.passed is False

    @pytest.mark.asyncio
    async def test_validate_quality_fail(self) -> None:
        """Test validation when quality fails."""
        config = ValidationConfig()
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "poor.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                with patch.object(service._quality_checker, "check", new_callable=AsyncMock) as mock_check:
                    with patch.object(service._test_runner, "run", new_callable=AsyncMock) as mock_run:
                        mock_scan.return_value = ScanResult(passed=True)
                        mock_check.return_value = QualityResult(passed=False, lint_score=20.0)
                        mock_run.return_value = TestResult(passed=True)

                        result = await service.validate(Path(temp_dir))

        assert result.status == ValidationStatus.FAILED
        assert result.quality_result is not None
        assert result.quality_result.passed is False

    @pytest.mark.asyncio
    async def test_validate_tests_fail(self) -> None:
        """Test validation when tests fail."""
        config = ValidationConfig()
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "tested.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                with patch.object(service._quality_checker, "check", new_callable=AsyncMock) as mock_check:
                    with patch.object(service._test_runner, "run", new_callable=AsyncMock) as mock_run:
                        mock_scan.return_value = ScanResult(passed=True)
                        mock_check.return_value = QualityResult(passed=True, lint_score=100.0)
                        mock_run.return_value = TestResult(passed=False, failed_tests=2)

                        result = await service.validate(Path(temp_dir))

        assert result.status == ValidationStatus.FAILED
        assert result.test_result is not None
        assert result.test_result.passed is False

    @pytest.mark.asyncio
    async def test_validate_skip_security(self) -> None:
        """Test validation with security skipped."""
        config = ValidationConfig(skip_security=True)
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "code.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                with patch.object(service._quality_checker, "check", new_callable=AsyncMock) as mock_check:
                    with patch.object(service._test_runner, "run", new_callable=AsyncMock) as mock_run:
                        mock_check.return_value = QualityResult(passed=True, lint_score=100.0)
                        mock_run.return_value = TestResult(passed=True)

                        result = await service.validate(Path(temp_dir))

        # Security should not have been called
        mock_scan.assert_not_called()
        assert result.security_result is None

    @pytest.mark.asyncio
    async def test_validate_skip_quality(self) -> None:
        """Test validation with quality skipped."""
        config = ValidationConfig(skip_quality=True)
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "code.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                with patch.object(service._quality_checker, "check", new_callable=AsyncMock) as mock_check:
                    with patch.object(service._test_runner, "run", new_callable=AsyncMock) as mock_run:
                        mock_scan.return_value = ScanResult(passed=True)
                        mock_run.return_value = TestResult(passed=True)

                        result = await service.validate(Path(temp_dir))

        mock_check.assert_not_called()
        assert result.quality_result is None

    @pytest.mark.asyncio
    async def test_validate_skip_tests(self) -> None:
        """Test validation with tests skipped."""
        config = ValidationConfig(skip_tests=True)
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "code.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                with patch.object(service._quality_checker, "check", new_callable=AsyncMock) as mock_check:
                    with patch.object(service._test_runner, "run", new_callable=AsyncMock) as mock_run:
                        mock_scan.return_value = ScanResult(passed=True)
                        mock_check.return_value = QualityResult(passed=True, lint_score=100.0)

                        result = await service.validate(Path(temp_dir))

        mock_run.assert_not_called()
        assert result.test_result is None

    @pytest.mark.asyncio
    async def test_validate_error_handling(self) -> None:
        """Test validation error handling."""
        config = ValidationConfig()
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "code.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                mock_scan.side_effect = Exception("Scan failed unexpectedly")

                result = await service.validate(Path(temp_dir))

        assert result.status == ValidationStatus.ERROR
        assert result.error_message == "Scan failed unexpectedly"

    @pytest.mark.asyncio
    async def test_validate_security_only(self) -> None:
        """Test security-only validation."""
        service = ValidationService()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "code.py"
            code_file.write_text("x = 1")

            with patch.object(service._scanner, "scan", new_callable=AsyncMock) as mock_scan:
                mock_scan.return_value = ScanResult(passed=True)

                result = await service.validate_security_only(Path(temp_dir))

        assert result.passed is True
        mock_scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_quality_only(self) -> None:
        """Test quality-only validation."""
        service = ValidationService()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "code.py"
            code_file.write_text("x = 1")

            with patch.object(service._quality_checker, "check", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = QualityResult(passed=True, lint_score=100.0)

                result = await service.validate_quality_only(Path(temp_dir))

        assert result.passed is True
        mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_tests_only(self) -> None:
        """Test tests-only validation."""
        service = ValidationService()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test_code.py"
            code_file.write_text("def test_x(): pass")

            with patch.object(service._test_runner, "run", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = TestResult(passed=True)

                result = await service.validate_tests_only(Path(temp_dir))

        assert result.passed is True
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_duration_tracked(self) -> None:
        """Test that validation duration is tracked."""
        config = ValidationConfig(skip_security=True, skip_quality=True, skip_tests=True)
        service = ValidationService(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = await service.validate(Path(temp_dir))

        # Duration should be non-negative (may be 0.0 if execution is very fast)
        assert result.total_duration_seconds >= 0


class TestGetValidationService:
    """Tests for get_validation_service singleton."""

    def test_returns_singleton(self) -> None:
        """Test that same instance is returned."""
        # Reset singleton
        import agent_marketplace_api.services.validation_service as vs

        vs._validation_service = None

        service1 = get_validation_service()
        service2 = get_validation_service()

        assert service1 is service2

    def test_uses_config_on_first_call(self) -> None:
        """Test that config is used on first call."""
        import agent_marketplace_api.services.validation_service as vs

        vs._validation_service = None

        config = ValidationConfig(max_lint_issues=99)
        service = get_validation_service(config)

        assert service.config.max_lint_issues == 99

"""Validation service for orchestrating agent validation."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from agent_marketplace_api.validation.quality import QualityChecker, QualityResult
from agent_marketplace_api.validation.runner import TestResult, TestRunner
from agent_marketplace_api.validation.scanner import ScanResult, SecurityScanner


class ValidationStatus(str, Enum):
    """Status of validation."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Complete validation result."""

    status: ValidationStatus
    security_result: ScanResult | None = None
    quality_result: QualityResult | None = None
    test_result: TestResult | None = None
    error_message: str | None = None
    total_duration_seconds: float = 0.0

    @property
    def passed(self) -> bool:
        """Check if all validations passed."""
        return self.status == ValidationStatus.PASSED

    @property
    def details(self) -> dict[str, bool]:
        """Get pass/fail details for each check."""
        return {
            "security": self.security_result.passed if self.security_result else False,
            "quality": self.quality_result.passed if self.quality_result else False,
            "tests": self.test_result.passed if self.test_result else False,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "status": self.status.value,
            "passed": self.passed,
            "details": self.details,
            "error_message": self.error_message,
            "total_duration_seconds": self.total_duration_seconds,
            "security": {
                "passed": self.security_result.passed if self.security_result else None,
                "issues_count": len(self.security_result.issues) if self.security_result else 0,
                "critical_count": self.security_result.critical_count
                if self.security_result
                else 0,
                "high_count": self.security_result.high_count if self.security_result else 0,
            }
            if self.security_result
            else None,
            "quality": {
                "passed": self.quality_result.passed if self.quality_result else None,
                "lint_score": self.quality_result.lint_score if self.quality_result else 0,
                "issues_count": len(self.quality_result.issues) if self.quality_result else 0,
            }
            if self.quality_result
            else None,
            "tests": {
                "passed": self.test_result.passed if self.test_result else None,
                "total": self.test_result.total_tests if self.test_result else 0,
                "passed_count": self.test_result.passed_tests if self.test_result else 0,
                "failed_count": self.test_result.failed_tests if self.test_result else 0,
                "coverage": self.test_result.coverage_percent if self.test_result else None,
            }
            if self.test_result
            else None,
        }


@dataclass
class ValidationConfig:
    """Configuration for validation pipeline."""

    # Security settings
    security_severity_threshold: str = "medium"
    security_timeout: int = 300

    # Quality settings
    max_lint_issues: int = 10
    require_type_hints: bool = False
    quality_timeout: int = 300

    # Test settings
    require_tests: bool = False
    min_coverage: float | None = None
    test_timeout: int = 600

    # Pipeline settings
    skip_security: bool = False
    skip_quality: bool = False
    skip_tests: bool = False


class ValidationService:
    """Service for validating agent code.

    Orchestrates security scanning, quality checking, and test execution.
    """

    def __init__(self, config: ValidationConfig | None = None) -> None:
        """Initialize validation service.

        Args:
            config: Validation configuration (uses defaults if not provided)
        """
        self.config = config or ValidationConfig()

        # Initialize validators
        self._scanner = SecurityScanner(
            severity_threshold=self.config.security_severity_threshold,
            timeout_seconds=self.config.security_timeout,
        )
        self._quality_checker = QualityChecker(
            max_lint_issues=self.config.max_lint_issues,
            require_type_hints=self.config.require_type_hints,
            timeout_seconds=self.config.quality_timeout,
        )
        self._test_runner = TestRunner(
            require_tests=self.config.require_tests,
            min_coverage=self.config.min_coverage,
            timeout_seconds=self.config.test_timeout,
        )

    async def validate(self, code_path: Path) -> ValidationResult:
        """Run full validation pipeline on code.

        Args:
            code_path: Path to the code to validate

        Returns:
            ValidationResult with all check results
        """
        import time

        start_time = time.time()

        security_result: ScanResult | None = None
        quality_result: QualityResult | None = None
        test_result: TestResult | None = None
        error_message: str | None = None

        try:
            # Security scan
            if not self.config.skip_security:
                security_result = await self._scanner.scan(code_path)

            # Quality check
            if not self.config.skip_quality:
                quality_result = await self._quality_checker.check(code_path)

            # Run tests
            if not self.config.skip_tests:
                test_result = await self._test_runner.run(code_path)

            # Determine overall status
            all_passed = True
            if security_result and not security_result.passed:
                all_passed = False
            if quality_result and not quality_result.passed:
                all_passed = False
            if test_result and not test_result.passed:
                all_passed = False

            status = ValidationStatus.PASSED if all_passed else ValidationStatus.FAILED

        except Exception as e:
            status = ValidationStatus.ERROR
            error_message = str(e)

        total_duration = time.time() - start_time

        return ValidationResult(
            status=status,
            security_result=security_result,
            quality_result=quality_result,
            test_result=test_result,
            error_message=error_message,
            total_duration_seconds=total_duration,
        )

    async def validate_security_only(self, code_path: Path) -> ScanResult:
        """Run only security scanning.

        Args:
            code_path: Path to scan

        Returns:
            ScanResult with findings
        """
        return await self._scanner.scan(code_path)

    async def validate_quality_only(self, code_path: Path) -> QualityResult:
        """Run only quality checking.

        Args:
            code_path: Path to check

        Returns:
            QualityResult with findings
        """
        return await self._quality_checker.check(code_path)

    async def validate_tests_only(self, code_path: Path) -> TestResult:
        """Run only tests.

        Args:
            code_path: Path to test

        Returns:
            TestResult with test outcomes
        """
        return await self._test_runner.run(code_path)


# Singleton instance
_validation_service: ValidationService | None = None


def get_validation_service(config: ValidationConfig | None = None) -> ValidationService:
    """Get or create the validation service singleton.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        ValidationService instance
    """
    global _validation_service
    if _validation_service is None:
        _validation_service = ValidationService(config)
    return _validation_service

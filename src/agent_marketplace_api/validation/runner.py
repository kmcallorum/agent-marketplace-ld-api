"""Test runner for agent code."""

import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class RunnerError(Exception):
    """Error during test execution."""


@dataclass
class TestCase:
    """A single test case result."""

    name: str
    status: str  # passed, failed, skipped, error
    duration_seconds: float = 0.0
    error_message: str | None = None
    file_path: str | None = None


@dataclass
class TestResult:
    """Result of running tests."""

    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    test_cases: list[TestCase] = field(default_factory=list)
    coverage_percent: float | None = None
    run_duration_seconds: float = 0.0
    output: str = ""

    @property
    def pass_rate(self) -> float:
        """Calculate test pass rate."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100.0


class TestRunner:
    """Test runner for Python agent code.

    Executes pytest with optional coverage reporting.
    """

    def __init__(
        self,
        require_tests: bool = True,
        min_coverage: float | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        """Initialize the test runner.

        Args:
            require_tests: Whether to require tests to exist
            min_coverage: Minimum required coverage percentage (None to skip)
            timeout_seconds: Maximum time to run tests
        """
        self.require_tests = require_tests
        self.min_coverage = min_coverage
        self.timeout_seconds = timeout_seconds

    async def run(self, code_path: Path) -> TestResult:
        """Run tests for the code.

        Args:
            code_path: Path to the code directory to test

        Returns:
            TestResult with findings

        Raises:
            RunnerError: If test execution fails
        """
        import time

        start_time = time.time()

        if not code_path.exists():
            raise RunnerError(f"Path does not exist: {code_path}")

        # Find test files
        test_files = await self._find_tests(code_path)

        if not test_files and self.require_tests:
            return TestResult(
                passed=False,
                output="No test files found",
                run_duration_seconds=time.time() - start_time,
            )

        if not test_files:
            # No tests required, no tests found - pass
            return TestResult(
                passed=True,
                output="No tests to run",
                run_duration_seconds=time.time() - start_time,
            )

        # Run pytest
        result = await self._run_pytest(code_path)

        result.run_duration_seconds = time.time() - start_time

        # Check coverage threshold if specified
        if (
            self.min_coverage is not None
            and result.coverage_percent is not None
            and result.coverage_percent < self.min_coverage
        ):
            result.passed = False

        return result

    async def _find_tests(self, code_path: Path) -> list[Path]:
        """Find test files in the code path.

        Args:
            code_path: Path to search for tests

        Returns:
            List of test file paths
        """
        test_files: list[Path] = []

        if code_path.is_file():
            if code_path.name.startswith("test_") or code_path.name.endswith("_test.py"):
                test_files.append(code_path)
        else:
            # Look for test files
            test_files.extend(code_path.rglob("test_*.py"))
            test_files.extend(code_path.rglob("*_test.py"))

            # Also check for tests/ directory
            tests_dir = code_path / "tests"
            if tests_dir.exists():
                test_files.extend(tests_dir.rglob("*.py"))

        return test_files

    async def _run_pytest(self, code_path: Path) -> TestResult:
        """Run pytest on the code path.

        Args:
            code_path: Path to test

        Returns:
            TestResult with test outcomes
        """
        # Build pytest command
        cmd = [
            "pytest",
            str(code_path),
            "-v",
            "--tb=short",
            "-q",
        ]

        # Add coverage if threshold specified
        if self.min_coverage is not None:
            cmd.extend([
                f"--cov={code_path}",
                "--cov-report=term-missing",
            ])

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=str(code_path.parent) if code_path.is_file() else str(code_path),
            )

            # Parse pytest output
            return self._parse_pytest_output(result.stdout, result.stderr, result.returncode)

        except subprocess.TimeoutExpired as e:
            raise RunnerError(f"Tests timed out after {self.timeout_seconds}s") from e
        except FileNotFoundError:
            # Pytest not installed
            return TestResult(
                passed=False,
                output="pytest not available",
            )

    def _parse_pytest_output(
        self,
        stdout: str,
        stderr: str,
        return_code: int,
    ) -> TestResult:
        """Parse pytest output to extract results.

        Args:
            stdout: Standard output from pytest
            stderr: Standard error from pytest
            return_code: Exit code from pytest

        Returns:
            TestResult parsed from output
        """
        import re

        test_cases: list[TestCase] = []
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        error_tests = 0
        coverage_percent: float | None = None

        output = stdout + "\n" + stderr

        # Parse test results from output
        # Format: test_file.py::test_name PASSED/FAILED/SKIPPED
        test_pattern = re.compile(r"(\S+::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)")
        for match in test_pattern.finditer(output):
            name, status = match.groups()
            status_lower = status.lower()
            test_cases.append(
                TestCase(
                    name=name,
                    status=status_lower,
                )
            )
            if status_lower == "passed":
                passed_tests += 1
            elif status_lower == "failed":
                failed_tests += 1
            elif status_lower == "skipped":
                skipped_tests += 1
            elif status_lower == "error":
                error_tests += 1

        # Parse summary line
        # Format: "X passed, Y failed, Z skipped" or similar
        summary_pattern = re.compile(
            r"(\d+)\s+passed(?:.*?(\d+)\s+failed)?(?:.*?(\d+)\s+skipped)?(?:.*?(\d+)\s+error)?"
        )
        summary_match = summary_pattern.search(output)
        if summary_match:
            groups = summary_match.groups()
            if groups[0]:
                passed_tests = int(groups[0])
            if groups[1]:
                failed_tests = int(groups[1])
            if groups[2]:
                skipped_tests = int(groups[2])
            if groups[3]:
                error_tests = int(groups[3])

        # Parse coverage percentage
        # Format: "TOTAL ... XX%"
        coverage_pattern = re.compile(r"TOTAL\s+\d+\s+\d+\s+(\d+)%")
        coverage_match = coverage_pattern.search(output)
        if coverage_match:
            coverage_percent = float(coverage_match.group(1))

        total_tests = passed_tests + failed_tests + skipped_tests + error_tests
        passed = return_code == 0 and failed_tests == 0 and error_tests == 0

        return TestResult(
            passed=passed,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            error_tests=error_tests,
            test_cases=test_cases,
            coverage_percent=coverage_percent,
            output=output,
        )

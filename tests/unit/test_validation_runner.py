"""Unit tests for test runner."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_marketplace_api.validation.runner import (
    RunnerError,
    TestCase,
    TestResult,
    TestRunner,
)


class TestTestCase:
    """Tests for TestCase dataclass."""

    def test_test_case_creation(self) -> None:
        """Test creating a test case."""
        case = TestCase(
            name="test_something",
            status="passed",
            duration_seconds=0.5,
            file_path="test_app.py",
        )

        assert case.name == "test_something"
        assert case.status == "passed"
        assert case.duration_seconds == 0.5
        assert case.file_path == "test_app.py"
        assert case.error_message is None

    def test_test_case_failed(self) -> None:
        """Test creating a failed test case."""
        case = TestCase(
            name="test_failing",
            status="failed",
            error_message="AssertionError: 1 != 2",
        )

        assert case.status == "failed"
        assert case.error_message == "AssertionError: 1 != 2"


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_test_result_passed(self) -> None:
        """Test passed test result."""
        result = TestResult(
            passed=True,
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
        )

        assert result.passed is True
        assert result.pass_rate == 100.0

    def test_test_result_partial_pass(self) -> None:
        """Test partial pass test result."""
        result = TestResult(
            passed=False,
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            skipped_tests=0,
        )

        assert result.passed is False
        assert result.pass_rate == 80.0

    def test_test_result_no_tests(self) -> None:
        """Test result with no tests."""
        result = TestResult(passed=True, total_tests=0)

        assert result.pass_rate == 0.0

    def test_test_result_with_coverage(self) -> None:
        """Test result with coverage."""
        result = TestResult(
            passed=True,
            total_tests=5,
            passed_tests=5,
            coverage_percent=85.5,
        )

        assert result.coverage_percent == 85.5


class TestTestRunner:
    """Tests for TestRunner."""

    def test_runner_initialization(self) -> None:
        """Test runner initialization with defaults."""
        runner = TestRunner()

        assert runner.require_tests is True
        assert runner.min_coverage is None
        assert runner.timeout_seconds == 600

    def test_runner_custom_config(self) -> None:
        """Test runner with custom configuration."""
        runner = TestRunner(
            require_tests=False,
            min_coverage=80.0,
            timeout_seconds=300,
        )

        assert runner.require_tests is False
        assert runner.min_coverage == 80.0
        assert runner.timeout_seconds == 300

    @pytest.mark.asyncio
    async def test_run_nonexistent_path(self) -> None:
        """Test running on non-existent path raises error."""
        runner = TestRunner()

        with pytest.raises(RunnerError, match="Path does not exist"):
            await runner.run(Path("/nonexistent/path"))

    @pytest.mark.asyncio
    async def test_run_no_tests_required(self) -> None:
        """Test running when no tests exist and not required."""
        runner = TestRunner(require_tests=False)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a non-test Python file
            code_file = Path(temp_dir) / "app.py"
            code_file.write_text("x = 1")

            result = await runner.run(Path(temp_dir))

        assert result.passed is True
        assert result.output == "No tests to run"

    @pytest.mark.asyncio
    async def test_run_no_tests_required_but_fails(self) -> None:
        """Test running when tests are required but don't exist."""
        runner = TestRunner(require_tests=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "app.py"
            code_file.write_text("x = 1")

            result = await runner.run(Path(temp_dir))

        assert result.passed is False
        assert "No test files found" in result.output

    @pytest.mark.asyncio
    async def test_run_with_passing_tests(self) -> None:
        """Test running with passing tests."""
        runner = TestRunner()

        pytest_output = """
test_app.py::test_one PASSED
test_app.py::test_two PASSED
test_app.py::test_three PASSED

3 passed in 0.05s
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("def test_one(): pass")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=pytest_output,
                    stderr="",
                    returncode=0,
                )
                result = await runner.run(Path(temp_dir))

        assert result.passed is True
        assert result.passed_tests == 3
        assert result.failed_tests == 0

    @pytest.mark.asyncio
    async def test_run_with_failing_tests(self) -> None:
        """Test running with failing tests."""
        runner = TestRunner()

        pytest_output = """
test_app.py::test_one PASSED
test_app.py::test_two FAILED
test_app.py::test_three PASSED

2 passed, 1 failed in 0.10s
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("def test_one(): pass")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=pytest_output,
                    stderr="",
                    returncode=1,
                )
                result = await runner.run(Path(temp_dir))

        assert result.passed is False
        assert result.passed_tests == 2
        assert result.failed_tests == 1

    @pytest.mark.asyncio
    async def test_run_with_skipped_tests(self) -> None:
        """Test running with skipped tests."""
        runner = TestRunner()

        pytest_output = """
test_app.py::test_one PASSED
test_app.py::test_two SKIPPED
test_app.py::test_three PASSED

2 passed, 1 skipped in 0.05s
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("def test_one(): pass")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=pytest_output,
                    stderr="",
                    returncode=0,
                )
                result = await runner.run(Path(temp_dir))

        assert result.passed is True
        assert result.passed_tests == 2
        assert result.skipped_tests == 1

    @pytest.mark.asyncio
    async def test_run_with_error_tests(self) -> None:
        """Test running with error tests."""
        runner = TestRunner()

        pytest_output = """
test_app.py::test_one PASSED
test_app.py::test_two ERROR

1 passed, 1 error in 0.05s
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("def test_one(): pass")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=pytest_output,
                    stderr="",
                    returncode=1,
                )
                result = await runner.run(Path(temp_dir))

        assert result.passed is False
        assert result.error_tests >= 1

    @pytest.mark.asyncio
    async def test_run_with_coverage(self) -> None:
        """Test running with coverage tracking."""
        runner = TestRunner(min_coverage=80.0)

        pytest_output = """
test_app.py::test_one PASSED

1 passed in 0.05s

Name          Stmts   Miss  Cover
---------------------------------
app.py           10      2    80%
---------------------------------
TOTAL            10      2    80%
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("def test_one(): pass")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=pytest_output,
                    stderr="",
                    returncode=0,
                )
                result = await runner.run(Path(temp_dir))

        assert result.passed is True
        assert result.coverage_percent == 80.0

    @pytest.mark.asyncio
    async def test_run_coverage_below_threshold(self) -> None:
        """Test running with coverage below threshold."""
        runner = TestRunner(min_coverage=90.0)

        pytest_output = """
test_app.py::test_one PASSED

1 passed in 0.05s

TOTAL            10      3    70%
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("def test_one(): pass")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=pytest_output,
                    stderr="",
                    returncode=0,
                )
                result = await runner.run(Path(temp_dir))

        assert result.passed is False  # 70% < 90% threshold
        assert result.coverage_percent == 70.0

    @pytest.mark.asyncio
    async def test_run_timeout(self) -> None:
        """Test handling pytest timeout."""
        runner = TestRunner(timeout_seconds=1)

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("def test_one(): pass")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("pytest", 1)

                with pytest.raises(RunnerError, match="timed out"):
                    await runner.run(Path(temp_dir))

    @pytest.mark.asyncio
    async def test_run_pytest_not_installed(self) -> None:
        """Test handling pytest not being installed."""
        runner = TestRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("def test_one(): pass")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError()

                result = await runner.run(Path(temp_dir))

        assert result.passed is False
        assert "pytest not available" in result.output

    @pytest.mark.asyncio
    async def test_find_tests_test_prefix(self) -> None:
        """Test finding test files with test_ prefix."""
        runner = TestRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "test_app.py").write_text("pass")
            Path(temp_dir, "test_utils.py").write_text("pass")
            Path(temp_dir, "app.py").write_text("pass")

            files = await runner._find_tests(Path(temp_dir))

        assert len(files) == 2
        assert all(f.name.startswith("test_") for f in files)

    @pytest.mark.asyncio
    async def test_find_tests_test_suffix(self) -> None:
        """Test finding test files with _test suffix."""
        runner = TestRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "app_test.py").write_text("pass")
            Path(temp_dir, "utils_test.py").write_text("pass")

            files = await runner._find_tests(Path(temp_dir))

        assert len(files) == 2
        assert all(f.name.endswith("_test.py") for f in files)

    @pytest.mark.asyncio
    async def test_find_tests_in_tests_directory(self) -> None:
        """Test finding tests in tests/ directory."""
        runner = TestRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            tests_dir = Path(temp_dir) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_app.py").write_text("pass")
            (tests_dir / "conftest.py").write_text("pass")

            files = await runner._find_tests(Path(temp_dir))

        assert len(files) >= 2

    @pytest.mark.asyncio
    async def test_find_tests_single_file(self) -> None:
        """Test finding tests from single test file."""
        runner = TestRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_app.py"
            test_file.write_text("pass")

            files = await runner._find_tests(test_file)

        assert len(files) == 1
        assert files[0] == test_file

    @pytest.mark.asyncio
    async def test_find_tests_non_test_file(self) -> None:
        """Test finding tests from non-test file returns empty."""
        runner = TestRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "app.py"
            code_file.write_text("pass")

            files = await runner._find_tests(code_file)

        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_run_duration_tracked(self) -> None:
        """Test that run duration is tracked."""
        runner = TestRunner(require_tests=False)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "app.py"
            code_file.write_text("x = 1")

            result = await runner.run(Path(temp_dir))

        assert result.run_duration_seconds > 0

    def test_parse_pytest_output_full_summary(self) -> None:
        """Test parsing full pytest summary."""
        runner = TestRunner()

        output = """
test_app.py::test_one PASSED
test_app.py::test_two PASSED
test_app.py::test_three FAILED
test_app.py::test_four SKIPPED

2 passed, 1 failed, 1 skipped in 0.15s
"""

        result = runner._parse_pytest_output(output, "", 1)

        assert result.passed is False
        assert result.passed_tests == 2
        assert result.failed_tests == 1
        assert result.skipped_tests == 1
        assert result.total_tests == 4

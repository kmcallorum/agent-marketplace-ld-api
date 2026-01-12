"""Unit tests for quality checker."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_marketplace_api.validation.quality import (
    QualityChecker,
    QualityError,
    QualityIssue,
    QualityResult,
)


class TestQualityIssue:
    """Tests for QualityIssue dataclass."""

    def test_quality_issue_creation(self) -> None:
        """Test creating a quality issue."""
        issue = QualityIssue(
            category="lint",
            code="E501",
            message="Line too long",
            file_path="app.py",
            line_number=42,
            column=80,
        )

        assert issue.category == "lint"
        assert issue.code == "E501"
        assert issue.message == "Line too long"
        assert issue.file_path == "app.py"
        assert issue.line_number == 42
        assert issue.column == 80

    def test_quality_issue_minimal(self) -> None:
        """Test creating issue with minimal fields."""
        issue = QualityIssue(
            category="type",
            code="mypy-error",
            message="Type error",
        )

        assert issue.category == "type"
        assert issue.file_path is None
        assert issue.line_number is None
        assert issue.column is None


class TestQualityResult:
    """Tests for QualityResult dataclass."""

    def test_quality_result_passed(self) -> None:
        """Test passed quality result."""
        result = QualityResult(passed=True, issues=[], lint_score=100.0)

        assert result.passed is True
        assert result.lint_score == 100.0
        assert result.lint_issues == []
        assert result.type_issues == []
        assert result.style_issues == []

    def test_quality_result_with_issues(self) -> None:
        """Test quality result with various issues."""
        issues = [
            QualityIssue(category="lint", code="E501", message="Line too long"),
            QualityIssue(category="lint", code="E302", message="Expected blank lines"),
            QualityIssue(category="type", code="mypy-error", message="Type mismatch"),
            QualityIssue(category="style", code="S001", message="Style issue"),
        ]
        result = QualityResult(passed=False, issues=issues, lint_score=80.0)

        assert result.passed is False
        assert len(result.lint_issues) == 2
        assert len(result.type_issues) == 1
        assert len(result.style_issues) == 1


class TestQualityChecker:
    """Tests for QualityChecker."""

    def test_checker_initialization(self) -> None:
        """Test checker initialization with defaults."""
        checker = QualityChecker()

        assert checker.max_lint_issues == 10
        assert checker.require_type_hints is False
        assert checker.timeout_seconds == 300

    def test_checker_custom_config(self) -> None:
        """Test checker with custom configuration."""
        checker = QualityChecker(
            max_lint_issues=5,
            require_type_hints=True,
            timeout_seconds=600,
        )

        assert checker.max_lint_issues == 5
        assert checker.require_type_hints is True
        assert checker.timeout_seconds == 600

    @pytest.mark.asyncio
    async def test_check_nonexistent_path(self) -> None:
        """Test checking non-existent path raises error."""
        checker = QualityChecker()

        with pytest.raises(QualityError, match="Path does not exist"):
            await checker.check(Path("/nonexistent/path"))

    @pytest.mark.asyncio
    async def test_check_empty_directory(self) -> None:
        """Test checking empty directory."""
        checker = QualityChecker()

        with tempfile.TemporaryDirectory() as temp_dir, patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
            result = await checker.check(Path(temp_dir))

        assert result.passed is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_check_clean_code(self) -> None:
        """Test checking clean Python code."""
        checker = QualityChecker()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "clean.py"
            code_file.write_text('"""Module."""\n\nx = 1\n')

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
                result = await checker.check(Path(temp_dir))

        assert result.passed is True
        assert result.lint_score == 100.0

    @pytest.mark.asyncio
    async def test_check_with_lint_issues(self) -> None:
        """Test checking code with lint issues."""
        checker = QualityChecker(max_lint_issues=5)

        ruff_output = [
            {
                "code": "E501",
                "message": "Line too long (100 > 88 characters)",
                "filename": "test.py",
                "location": {"row": 10, "column": 89},
            },
            {
                "code": "F401",
                "message": "Unused import",
                "filename": "test.py",
                "location": {"row": 1, "column": 1},
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            import json

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=json.dumps(ruff_output),
                    stderr="",
                    returncode=1,
                )
                result = await checker.check(Path(temp_dir))

        assert result.passed is True  # 2 issues <= 5 max
        assert len(result.issues) == 2
        assert result.lint_score == 90.0  # 100 - (2 * 5)

    @pytest.mark.asyncio
    async def test_check_exceeds_max_issues(self) -> None:
        """Test checking code that exceeds max lint issues."""
        checker = QualityChecker(max_lint_issues=1)

        ruff_output = [
            {"code": "E501", "message": "Issue 1", "filename": "test.py", "location": {"row": 1}},
            {"code": "E502", "message": "Issue 2", "filename": "test.py", "location": {"row": 2}},
            {"code": "E503", "message": "Issue 3", "filename": "test.py", "location": {"row": 3}},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            import json

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=json.dumps(ruff_output),
                    stderr="",
                    returncode=1,
                )
                result = await checker.check(Path(temp_dir))

        assert result.passed is False  # 3 issues > 1 max
        assert len(result.issues) == 3

    @pytest.mark.asyncio
    async def test_check_with_type_hints_required(self) -> None:
        """Test checking with type hints required."""
        checker = QualityChecker(require_type_hints=True)

        mypy_output = "test.py:10: error: Missing return type annotation\n"

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                # First call is ruff (success), second is mypy (failure)
                mock_run.side_effect = [
                    MagicMock(stdout="[]", stderr="", returncode=0),  # ruff
                    MagicMock(stdout=mypy_output, stderr="", returncode=1),  # mypy
                ]
                result = await checker.check(Path(temp_dir))

        assert result.passed is False
        assert result.type_check_passed is False
        assert len(result.type_issues) == 1

    @pytest.mark.asyncio
    async def test_check_with_type_hints_passing(self) -> None:
        """Test checking with type hints that pass."""
        checker = QualityChecker(require_type_hints=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x: int = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    MagicMock(stdout="[]", stderr="", returncode=0),  # ruff
                    MagicMock(stdout="", stderr="", returncode=0),  # mypy
                ]
                result = await checker.check(Path(temp_dir))

        assert result.passed is True
        assert result.type_check_passed is True

    @pytest.mark.asyncio
    async def test_check_ruff_timeout(self) -> None:
        """Test handling ruff timeout."""
        checker = QualityChecker(timeout_seconds=1)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("ruff", 1)

                with pytest.raises(QualityError, match="timed out"):
                    await checker.check(Path(temp_dir))

    @pytest.mark.asyncio
    async def test_check_ruff_not_installed(self) -> None:
        """Test handling ruff not being installed."""
        checker = QualityChecker()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError()

                # Should not raise, just skip ruff
                result = await checker.check(Path(temp_dir))

        assert result is not None
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_check_mypy_timeout(self) -> None:
        """Test handling mypy timeout."""
        checker = QualityChecker(require_type_hints=True, timeout_seconds=1)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    MagicMock(stdout="[]", stderr="", returncode=0),  # ruff
                    subprocess.TimeoutExpired("mypy", 1),  # mypy timeout
                ]

                with pytest.raises(QualityError, match="timed out"):
                    await checker.check(Path(temp_dir))

    @pytest.mark.asyncio
    async def test_check_mypy_not_installed(self) -> None:
        """Test handling mypy not being installed."""
        checker = QualityChecker(require_type_hints=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    MagicMock(stdout="[]", stderr="", returncode=0),  # ruff
                    FileNotFoundError(),  # mypy not found
                ]

                result = await checker.check(Path(temp_dir))

        # Should still pass since mypy is not installed
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_check_lint_score_calculation(self) -> None:
        """Test lint score decreases with issues."""
        checker = QualityChecker(max_lint_issues=100)  # High max so we don't fail

        # Create 10 issues
        ruff_output = [
            {
                "code": f"E{i:03d}",
                "message": f"Issue {i}",
                "filename": "test.py",
                "location": {"row": i},
            }
            for i in range(10)
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            import json

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=json.dumps(ruff_output),
                    stderr="",
                    returncode=1,
                )
                result = await checker.check(Path(temp_dir))

        # 10 issues * 5 points each = 50, so score = 100 - 50 = 50
        assert result.lint_score == 50.0

    @pytest.mark.asyncio
    async def test_check_lint_score_minimum_zero(self) -> None:
        """Test lint score doesn't go below zero."""
        checker = QualityChecker(max_lint_issues=100)

        # Create 30 issues (would be -50 without floor)
        ruff_output = [
            {
                "code": f"E{i:03d}",
                "message": f"Issue {i}",
                "filename": "test.py",
                "location": {"row": i},
            }
            for i in range(30)
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            import json

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=json.dumps(ruff_output),
                    stderr="",
                    returncode=1,
                )
                result = await checker.check(Path(temp_dir))

        assert result.lint_score == 0.0

    @pytest.mark.asyncio
    async def test_check_invalid_ruff_json(self) -> None:
        """Test handling invalid JSON from ruff."""
        checker = QualityChecker()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="not valid json",
                    stderr="",
                    returncode=1,
                )
                result = await checker.check(Path(temp_dir))

        # Should not raise, just skip parsing
        assert result is not None

    @pytest.mark.asyncio
    async def test_check_duration_tracked(self) -> None:
        """Test that check duration is tracked."""
        checker = QualityChecker()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
                result = await checker.check(Path(temp_dir))

        assert result.check_duration_seconds > 0

    @pytest.mark.asyncio
    async def test_check_mypy_output_with_empty_lines(self) -> None:
        """Test mypy output parsing handles empty lines."""
        checker = QualityChecker(require_type_hints=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            # Mypy output with empty lines IN THE MIDDLE (strip removes leading/trailing)
            mypy_output = "test.py:1: error: first error\n\ntest.py:2: error: second error"

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    MagicMock(stdout="[]", stderr="", returncode=0),  # ruff
                    MagicMock(stdout=mypy_output, stderr="", returncode=1),  # mypy
                ]
                result = await checker.check(Path(temp_dir))

        # Should parse the errors but skip empty lines
        assert result.passed is False
        assert len([i for i in result.issues if i.category == "type"]) == 2

    @pytest.mark.asyncio
    async def test_check_mypy_output_non_matching_lines(self) -> None:
        """Test mypy output parsing skips non-matching lines."""
        checker = QualityChecker(require_type_hints=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            # Mypy output with non-matching format
            mypy_output = "Some summary line\ntest.py:1: error: actual error\nAnother line"

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    MagicMock(stdout="[]", stderr="", returncode=0),  # ruff
                    MagicMock(stdout=mypy_output, stderr="", returncode=1),  # mypy
                ]
                result = await checker.check(Path(temp_dir))

        # Should only find the matching line
        assert len([i for i in result.issues if i.category == "type"]) == 1

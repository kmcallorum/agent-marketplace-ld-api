"""Unit tests for security scanner."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_marketplace_api.validation.scanner import (
    ScanError,
    ScanResult,
    SecurityIssue,
    SecurityScanner,
)


class TestSecurityIssue:
    """Tests for SecurityIssue dataclass."""

    def test_security_issue_creation(self) -> None:
        """Test creating a security issue."""
        issue = SecurityIssue(
            severity="high",
            title="Potential SQL Injection",
            description="Use of raw SQL query",
            file_path="app.py",
            line_number=42,
        )

        assert issue.severity == "high"
        assert issue.title == "Potential SQL Injection"
        assert issue.description == "Use of raw SQL query"
        assert issue.file_path == "app.py"
        assert issue.line_number == 42

    def test_security_issue_minimal(self) -> None:
        """Test creating issue with minimal fields."""
        issue = SecurityIssue(
            severity="low",
            title="Minor issue",
            description="",
        )

        assert issue.severity == "low"
        assert issue.file_path is None
        assert issue.line_number is None


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_scan_result_passed(self) -> None:
        """Test passed scan result."""
        result = ScanResult(passed=True, issues=[])

        assert result.passed is True
        assert result.critical_count == 0
        assert result.high_count == 0
        assert result.medium_count == 0
        assert result.low_count == 0

    def test_scan_result_with_issues(self) -> None:
        """Test scan result with various severity issues."""
        issues = [
            SecurityIssue(severity="critical", title="Critical", description=""),
            SecurityIssue(severity="critical", title="Critical 2", description=""),
            SecurityIssue(severity="high", title="High", description=""),
            SecurityIssue(severity="medium", title="Medium", description=""),
            SecurityIssue(severity="low", title="Low", description=""),
            SecurityIssue(severity="low", title="Low 2", description=""),
        ]
        result = ScanResult(passed=False, issues=issues)

        assert result.passed is False
        assert result.critical_count == 2
        assert result.high_count == 1
        assert result.medium_count == 1
        assert result.low_count == 2


class TestSecurityScanner:
    """Tests for SecurityScanner."""

    def test_scanner_initialization(self) -> None:
        """Test scanner initialization with defaults."""
        scanner = SecurityScanner()

        assert scanner.severity_threshold == "medium"
        assert scanner.timeout_seconds == 300

    def test_scanner_custom_config(self) -> None:
        """Test scanner with custom configuration."""
        scanner = SecurityScanner(
            severity_threshold="high",
            timeout_seconds=600,
        )

        assert scanner.severity_threshold == "high"
        assert scanner.timeout_seconds == 600

    @pytest.mark.asyncio
    async def test_scan_nonexistent_path(self) -> None:
        """Test scanning non-existent path raises error."""
        scanner = SecurityScanner()

        with pytest.raises(ScanError, match="Path does not exist"):
            await scanner.scan(Path("/nonexistent/path"))

    @pytest.mark.asyncio
    async def test_scan_empty_directory(self) -> None:
        """Test scanning empty directory."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            result = await scanner.scan(Path(temp_dir))

        assert result.passed is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_scan_clean_code(self) -> None:
        """Test scanning clean Python code."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a clean Python file
            code_file = Path(temp_dir) / "clean.py"
            code_file.write_text("""
def hello(name: str) -> str:
    return f"Hello, {name}!"
""")
            result = await scanner.scan(Path(temp_dir))

        assert result.passed is True
        assert result.scan_duration_seconds > 0

    @pytest.mark.asyncio
    async def test_scan_detects_hardcoded_secret(self) -> None:
        """Test scanner detects hardcoded secrets."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file with a hardcoded secret
            code_file = Path(temp_dir) / "secrets.py"
            code_file.write_text('''
API_KEY = "sk-1234567890abcdef1234567890abcdef"
password = "mysecretpassword123"
''')
            result = await scanner.scan(Path(temp_dir))

        # Should detect the hardcoded secrets
        assert len(result.issues) > 0
        secret_titles = [i.title for i in result.issues]
        assert any("API key" in t or "password" in t for t in secret_titles)

    @pytest.mark.asyncio
    async def test_scan_ignores_comments(self) -> None:
        """Test scanner ignores secrets in comments."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "commented.py"
            code_file.write_text('''
# api_key = "sk-1234567890abcdef"
# This is just a comment about passwords
''')
            result = await scanner.scan(Path(temp_dir))

        # Should not flag comments
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_scan_single_file(self) -> None:
        """Test scanning a single Python file."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "single.py"
            code_file.write_text("x = 1")

            result = await scanner.scan(code_file)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_scan_with_bandit_mock(self) -> None:
        """Test scanning with mocked bandit output."""
        scanner = SecurityScanner()

        bandit_output = {
            "results": [
                {
                    "issue_severity": "HIGH",
                    "issue_text": "Use of exec detected",
                    "more_info": "https://...",
                    "filename": "test.py",
                    "line_number": 10,
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            import json

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=json.dumps(bandit_output),
                    stderr="",
                    returncode=1,
                )
                result = await scanner.scan(Path(temp_dir))

        # Should have the bandit issue
        assert len(result.issues) >= 1
        assert any(i.title == "Use of exec detected" for i in result.issues)

    @pytest.mark.asyncio
    async def test_scan_bandit_timeout(self) -> None:
        """Test handling bandit timeout."""
        import subprocess

        scanner = SecurityScanner(timeout_seconds=1)

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("bandit", 1)

                with pytest.raises(ScanError, match="timed out"):
                    await scanner.scan(Path(temp_dir))

    @pytest.mark.asyncio
    async def test_scan_bandit_not_installed(self) -> None:
        """Test handling bandit not being installed."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError()

                # Should not raise, just skip bandit
                result = await scanner.scan(Path(temp_dir))

        assert result is not None

    @pytest.mark.asyncio
    async def test_scan_severity_threshold_low(self) -> None:
        """Test severity threshold at low level."""
        scanner = SecurityScanner(severity_threshold="low")

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text('token = "test1234567890token"')

            result = await scanner.scan(Path(temp_dir))

        # With low threshold, even low severity issues should fail
        if result.issues:
            assert result.passed is False

    @pytest.mark.asyncio
    async def test_scan_severity_threshold_critical(self) -> None:
        """Test severity threshold at critical level."""
        scanner = SecurityScanner(severity_threshold="critical")

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            # High severity but not critical
            code_file.write_text('password = "secret123456"')

            result = await scanner.scan(Path(temp_dir))

        # With critical threshold, high severity should still pass
        # (unless there are critical issues)
        high_issues = [i for i in result.issues if i.severity == "high"]
        critical_issues = [i for i in result.issues if i.severity == "critical"]
        if high_issues and not critical_issues:
            assert result.passed is True

    @pytest.mark.asyncio
    async def test_scan_unreadable_file(self) -> None:
        """Test handling unreadable files gracefully."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a binary file that will fail to decode as text
            binary_file = Path(temp_dir) / "binary.py"
            binary_file.write_bytes(b"\x00\x01\x02\x03")

            # Should not raise, just skip the file
            result = await scanner.scan(Path(temp_dir))

        assert result is not None

    @pytest.mark.asyncio
    async def test_scan_bandit_invalid_json(self) -> None:
        """Test handling invalid JSON from bandit."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            with patch("subprocess.run") as mock_run:
                # Bandit returns invalid JSON
                mock_run.return_value = MagicMock(
                    stdout="not valid json at all",
                    stderr="",
                    returncode=0,
                )
                result = await scanner.scan(Path(temp_dir))

        # Should not raise, just skip parsing bandit output
        assert result is not None

    @pytest.mark.asyncio
    async def test_scan_file_read_error(self) -> None:
        """Test handling file read errors in secrets check."""
        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "test.py"
            code_file.write_text("x = 1")

            # Mock file read to raise OSError
            with patch("pathlib.Path.read_text", side_effect=OSError("Permission denied")):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(stdout="{}", stderr="", returncode=0)

                    # Should not raise, just skip the file
                    result = await scanner.scan(code_file)

        assert result is not None

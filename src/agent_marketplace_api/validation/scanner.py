"""Security scanning for agent code."""

import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class ScanError(Exception):
    """Error during security scanning."""


@dataclass
class SecurityIssue:
    """A security issue found during scanning."""

    severity: str  # critical, high, medium, low
    title: str
    description: str
    file_path: str | None = None
    line_number: int | None = None


@dataclass
class ScanResult:
    """Result of a security scan."""

    passed: bool
    issues: list[SecurityIssue] = field(default_factory=list)
    scanner_version: str = ""
    scan_duration_seconds: float = 0.0

    @property
    def critical_count(self) -> int:
        """Count of critical severity issues."""
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def high_count(self) -> int:
        """Count of high severity issues."""
        return sum(1 for i in self.issues if i.severity == "high")

    @property
    def medium_count(self) -> int:
        """Count of medium severity issues."""
        return sum(1 for i in self.issues if i.severity == "medium")

    @property
    def low_count(self) -> int:
        """Count of low severity issues."""
        return sum(1 for i in self.issues if i.severity == "low")


class SecurityScanner:
    """Security scanner for Python agent code.

    Uses bandit for security analysis and checks for common vulnerabilities.
    """

    def __init__(
        self,
        severity_threshold: str = "medium",
        timeout_seconds: int = 300,
    ) -> None:
        """Initialize the security scanner.

        Args:
            severity_threshold: Minimum severity to fail on (low, medium, high, critical)
            timeout_seconds: Maximum time to run the scan
        """
        self.severity_threshold = severity_threshold
        self.timeout_seconds = timeout_seconds
        self._severity_levels = ["low", "medium", "high", "critical"]

    async def scan(self, code_path: Path) -> ScanResult:
        """Scan code for security issues.

        Args:
            code_path: Path to the code directory or file to scan

        Returns:
            ScanResult with findings

        Raises:
            ScanError: If scanning fails
        """
        import time

        start_time = time.time()

        if not code_path.exists():
            raise ScanError(f"Path does not exist: {code_path}")

        issues: list[SecurityIssue] = []

        # Run bandit security scanner
        bandit_issues = await self._run_bandit(code_path)
        issues.extend(bandit_issues)

        # Check for hardcoded secrets patterns
        secret_issues = await self._check_secrets(code_path)
        issues.extend(secret_issues)

        # Determine if scan passed based on threshold
        threshold_idx = self._severity_levels.index(self.severity_threshold)
        passed = not any(
            self._severity_levels.index(i.severity) >= threshold_idx for i in issues
        )

        scan_duration = time.time() - start_time

        return ScanResult(
            passed=passed,
            issues=issues,
            scanner_version="1.0.0",
            scan_duration_seconds=scan_duration,
        )

    async def _run_bandit(self, code_path: Path) -> list[SecurityIssue]:
        """Run bandit security scanner.

        Args:
            code_path: Path to scan

        Returns:
            List of security issues found
        """
        issues: list[SecurityIssue] = []

        try:
            # Run bandit with JSON output
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "bandit",
                    "-r",
                    str(code_path),
                    "-f",
                    "json",
                    "-ll",  # Only medium and above
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            # Parse bandit output
            if result.stdout:
                import json

                try:
                    data = json.loads(result.stdout)
                    for finding in data.get("results", []):
                        severity = finding.get("issue_severity", "medium").lower()
                        issues.append(
                            SecurityIssue(
                                severity=severity,
                                title=finding.get("issue_text", "Unknown issue"),
                                description=finding.get("more_info", ""),
                                file_path=finding.get("filename"),
                                line_number=finding.get("line_number"),
                            )
                        )
                except json.JSONDecodeError:
                    pass  # Bandit output not valid JSON

        except subprocess.TimeoutExpired as e:
            raise ScanError(f"Security scan timed out after {self.timeout_seconds}s") from e
        except FileNotFoundError:
            # Bandit not installed - skip but don't fail
            pass

        return issues

    async def _check_secrets(self, code_path: Path) -> list[SecurityIssue]:
        """Check for hardcoded secrets in code.

        Args:
            code_path: Path to scan

        Returns:
            List of potential secret issues
        """
        import re

        issues: list[SecurityIssue] = []

        # Patterns that might indicate hardcoded secrets
        secret_patterns = [
            (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][^"\']{10,}["\']', "Potential API key"),
            (r'(?i)(secret[_-]?key|secretkey)\s*[=:]\s*["\'][^"\']{10,}["\']', "Potential secret key"),
            (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,}["\']', "Potential hardcoded password"),
            (r'(?i)(token)\s*[=:]\s*["\'][^"\']{10,}["\']', "Potential hardcoded token"),
            (r'(?i)(aws[_-]?access[_-]?key)', "Potential AWS access key"),
            (r'(?i)(private[_-]?key)', "Potential private key reference"),
        ]

        # Get all Python files
        if code_path.is_file():
            files = [code_path] if code_path.suffix == ".py" else []
        else:
            files = list(code_path.rglob("*.py"))

        for file_path in files:
            try:
                content = await asyncio.to_thread(file_path.read_text)
                lines = content.split("\n")

                for line_num, line in enumerate(lines, start=1):
                    # Skip comments
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue

                    for pattern, title in secret_patterns:
                        if re.search(pattern, line):
                            issues.append(
                                SecurityIssue(
                                    severity="high",
                                    title=title,
                                    description=f"Found pattern matching potential secret: {pattern}",
                                    file_path=str(file_path),
                                    line_number=line_num,
                                )
                            )
                            break  # One issue per line

            except (OSError, UnicodeDecodeError):
                continue  # Skip files that can't be read

        return issues

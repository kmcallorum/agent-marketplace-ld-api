"""Code quality checking for agent code."""

import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class QualityError(Exception):
    """Error during quality checking."""


@dataclass
class QualityIssue:
    """A code quality issue."""

    category: str  # lint, type, style
    code: str  # Rule code (e.g., E501, mypy-error)
    message: str
    file_path: str | None = None
    line_number: int | None = None
    column: int | None = None


@dataclass
class QualityResult:
    """Result of quality checking."""

    passed: bool
    issues: list[QualityIssue] = field(default_factory=list)
    lint_score: float = 0.0  # 0-100 score
    type_check_passed: bool = True
    check_duration_seconds: float = 0.0

    @property
    def lint_issues(self) -> list[QualityIssue]:
        """Get lint-related issues."""
        return [i for i in self.issues if i.category == "lint"]

    @property
    def type_issues(self) -> list[QualityIssue]:
        """Get type-related issues."""
        return [i for i in self.issues if i.category == "type"]

    @property
    def style_issues(self) -> list[QualityIssue]:
        """Get style-related issues."""
        return [i for i in self.issues if i.category == "style"]


class QualityChecker:
    """Code quality checker for Python agent code.

    Uses ruff for linting and mypy for type checking.
    """

    def __init__(
        self,
        max_lint_issues: int = 10,
        require_type_hints: bool = False,
        timeout_seconds: int = 300,
    ) -> None:
        """Initialize the quality checker.

        Args:
            max_lint_issues: Maximum allowed lint issues before failing
            require_type_hints: Whether to require type hints
            timeout_seconds: Maximum time to run checks
        """
        self.max_lint_issues = max_lint_issues
        self.require_type_hints = require_type_hints
        self.timeout_seconds = timeout_seconds

    async def check(self, code_path: Path) -> QualityResult:
        """Check code quality.

        Args:
            code_path: Path to the code directory or file to check

        Returns:
            QualityResult with findings

        Raises:
            QualityError: If checking fails
        """
        import time

        start_time = time.time()

        if not code_path.exists():
            raise QualityError(f"Path does not exist: {code_path}")

        issues: list[QualityIssue] = []

        # Run ruff linter
        lint_issues = await self._run_ruff(code_path)
        issues.extend(lint_issues)

        # Run mypy type checker if required
        type_check_passed = True
        if self.require_type_hints:
            type_issues, type_check_passed = await self._run_mypy(code_path)
            issues.extend(type_issues)

        # Calculate lint score (100 = perfect, decreases with issues)
        lint_issue_count = len([i for i in issues if i.category == "lint"])
        lint_score = max(0.0, 100.0 - (lint_issue_count * 5.0))

        # Determine if check passed
        passed = lint_issue_count <= self.max_lint_issues
        if self.require_type_hints:
            passed = passed and type_check_passed

        check_duration = time.time() - start_time

        return QualityResult(
            passed=passed,
            issues=issues,
            lint_score=lint_score,
            type_check_passed=type_check_passed,
            check_duration_seconds=check_duration,
        )

    async def _run_ruff(self, code_path: Path) -> list[QualityIssue]:
        """Run ruff linter.

        Args:
            code_path: Path to check

        Returns:
            List of lint issues found
        """
        issues: list[QualityIssue] = []

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "ruff",
                    "check",
                    str(code_path),
                    "--output-format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            # Parse ruff output
            if result.stdout:
                import json

                try:
                    findings = json.loads(result.stdout)
                    for finding in findings:
                        issues.append(
                            QualityIssue(
                                category="lint",
                                code=finding.get("code", "unknown"),
                                message=finding.get("message", "Unknown issue"),
                                file_path=finding.get("filename"),
                                line_number=finding.get("location", {}).get("row"),
                                column=finding.get("location", {}).get("column"),
                            )
                        )
                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired as e:
            raise QualityError(f"Lint check timed out after {self.timeout_seconds}s") from e
        except FileNotFoundError:
            # Ruff not installed - skip but don't fail
            pass

        return issues

    async def _run_mypy(self, code_path: Path) -> tuple[list[QualityIssue], bool]:
        """Run mypy type checker.

        Args:
            code_path: Path to check

        Returns:
            Tuple of (issues, passed)
        """
        issues: list[QualityIssue] = []
        passed = True

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "mypy",
                    str(code_path),
                    "--ignore-missing-imports",
                    "--no-error-summary",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            # Parse mypy output (format: file:line: error: message)
            if result.stdout:
                import re

                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue

                    match = re.match(r"(.+):(\d+): (\w+): (.+)", line)
                    if match:
                        file_path, line_num, severity, message = match.groups()
                        issues.append(
                            QualityIssue(
                                category="type",
                                code=f"mypy-{severity}",
                                message=message,
                                file_path=file_path,
                                line_number=int(line_num),
                            )
                        )
                        if severity == "error":
                            passed = False

            # Check return code
            if result.returncode != 0:
                passed = False

        except subprocess.TimeoutExpired as e:
            raise QualityError(f"Type check timed out after {self.timeout_seconds}s") from e
        except FileNotFoundError:
            # Mypy not installed - skip but don't fail
            pass

        return issues, passed

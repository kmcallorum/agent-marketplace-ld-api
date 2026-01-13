# Validation Pipeline

Automated validation system for agent submissions in agent-marketplace-api.

## Overview

Every agent submission goes through a multi-stage validation pipeline before becoming publicly available. The pipeline runs asynchronously via Celery workers to avoid blocking API responses.

```
Agent Upload → Queue Job → Security Scan → Quality Check → Compatibility Test → Test Run → Results
```

---

## Pipeline Components

### 1. Security Scanner (`validation/scanner.py`)

Scans agent code for security vulnerabilities.

**Checks:**
- Known vulnerabilities in dependencies (via Snyk or safety)
- Dangerous imports (os.system, subprocess, eval, exec)
- Hardcoded secrets/credentials
- Suspicious network calls
- File system access patterns

**Implementation:**
```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SecurityResult:
    passed: bool
    vulnerabilities: list[dict]
    warnings: list[str]
    scan_duration_ms: int

class SecurityScanner:
    """Scans agent code for security issues."""

    DANGEROUS_IMPORTS = [
        'os.system', 'subprocess', 'eval', 'exec',
        '__import__', 'importlib', 'pickle.loads',
    ]

    SECRET_PATTERNS = [
        r'(?i)(api[_-]?key|secret|password|token)\s*=\s*["\'][^"\']+["\']',
        r'(?i)bearer\s+[a-zA-Z0-9_-]+',
    ]

    async def scan(self, code_path: Path) -> SecurityResult:
        """Run security scan on agent code."""
        vulnerabilities = []
        warnings = []

        # Check for dangerous imports
        dangerous = await self._check_dangerous_imports(code_path)
        vulnerabilities.extend(dangerous)

        # Check for hardcoded secrets
        secrets = await self._check_secrets(code_path)
        vulnerabilities.extend(secrets)

        # Run dependency scan (Snyk/safety)
        dep_vulns = await self._scan_dependencies(code_path)
        vulnerabilities.extend(dep_vulns)

        return SecurityResult(
            passed=len(vulnerabilities) == 0,
            vulnerabilities=vulnerabilities,
            warnings=warnings,
            scan_duration_ms=elapsed,
        )

    async def _check_dangerous_imports(self, code_path: Path) -> list[dict]:
        """Check for dangerous imports in code."""
        # Implementation
        pass

    async def _check_secrets(self, code_path: Path) -> list[dict]:
        """Check for hardcoded secrets."""
        # Implementation using regex patterns
        pass

    async def _scan_dependencies(self, code_path: Path) -> list[dict]:
        """Scan dependencies for known vulnerabilities."""
        # Run: safety check or snyk test
        pass
```

---

### 2. Quality Checker (`validation/quality.py`)

Checks code quality using static analysis tools.

**Checks:**
- Linting (ruff)
- Type checking (mypy)
- Code complexity
- Documentation coverage

**Implementation:**
```python
@dataclass
class QualityResult:
    passed: bool
    score: float  # 0.0 - 1.0
    lint_errors: list[dict]
    type_errors: list[dict]
    complexity_issues: list[dict]

class QualityChecker:
    """Checks code quality of agent submissions."""

    MIN_QUALITY_SCORE = 0.7  # Minimum score to pass

    async def check(self, code_path: Path) -> QualityResult:
        """Run quality checks on agent code."""
        # Run ruff
        lint_result = await self._run_ruff(code_path)

        # Run mypy
        type_result = await self._run_mypy(code_path)

        # Calculate complexity
        complexity = await self._check_complexity(code_path)

        # Calculate overall score
        score = self._calculate_score(lint_result, type_result, complexity)

        return QualityResult(
            passed=score >= self.MIN_QUALITY_SCORE,
            score=score,
            lint_errors=lint_result.errors,
            type_errors=type_result.errors,
            complexity_issues=complexity.issues,
        )

    async def _run_ruff(self, code_path: Path) -> LintResult:
        """Run ruff linter."""
        proc = await asyncio.create_subprocess_exec(
            'ruff', 'check', str(code_path), '--format=json',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return LintResult.from_json(stdout)

    async def _run_mypy(self, code_path: Path) -> TypeResult:
        """Run mypy type checker."""
        proc = await asyncio.create_subprocess_exec(
            'mypy', str(code_path), '--json-report', '-',
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return TypeResult.from_json(stdout)

    def _calculate_score(
        self,
        lint: LintResult,
        types: TypeResult,
        complexity: ComplexityResult,
    ) -> float:
        """Calculate overall quality score."""
        # Weighted average
        weights = {'lint': 0.4, 'types': 0.4, 'complexity': 0.2}
        return (
            weights['lint'] * lint.score +
            weights['types'] * types.score +
            weights['complexity'] * complexity.score
        )
```

---

### 3. Compatibility Checker (`validation/compatibility.py`)

Verifies agent is compatible with pytest-agents framework.

**Checks:**
- Required imports present
- Agent class structure correct
- Required methods implemented
- Configuration valid

**Implementation:**
```python
@dataclass
class CompatibilityResult:
    passed: bool
    errors: list[str]
    warnings: list[str]
    pytest_agents_version: str | None

class CompatibilityChecker:
    """Checks pytest-agents compatibility."""

    REQUIRED_IMPORTS = ['pytest_agents']
    REQUIRED_DECORATORS = ['@agent', '@pytest_agents.agent']

    async def check(self, code_path: Path) -> CompatibilityResult:
        """Check pytest-agents compatibility."""
        errors = []
        warnings = []

        # Check imports
        if not await self._has_required_imports(code_path):
            errors.append("Missing pytest_agents import")

        # Check agent decorator
        if not await self._has_agent_decorator(code_path):
            errors.append("No @agent decorator found")

        # Check agent structure
        structure_errors = await self._validate_agent_structure(code_path)
        errors.extend(structure_errors)

        # Get pytest-agents version from requirements
        version = await self._get_pytest_agents_version(code_path)

        return CompatibilityResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            pytest_agents_version=version,
        )

    async def _has_required_imports(self, code_path: Path) -> bool:
        """Check for required imports."""
        # Parse AST and check imports
        pass

    async def _has_agent_decorator(self, code_path: Path) -> bool:
        """Check for @agent decorator."""
        # Parse AST and check decorators
        pass

    async def _validate_agent_structure(self, code_path: Path) -> list[str]:
        """Validate agent class structure."""
        # Check required methods, attributes
        pass
```

---

### 4. Test Runner (`validation/runner.py`)

Executes agent's test suite in isolated environment.

**Features:**
- Sandboxed execution (Docker container)
- Timeout enforcement
- Resource limits (CPU, memory)
- Test result collection

**Implementation:**
```python
@dataclass
class TestResult:
    passed: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    duration_ms: int
    output: str
    coverage: float | None

class TestRunner:
    """Runs agent tests in isolated environment."""

    TIMEOUT_SECONDS = 300  # 5 minutes max
    MEMORY_LIMIT = "512m"
    CPU_LIMIT = "1.0"

    async def run_tests(self, code_path: Path) -> TestResult:
        """Run agent tests in Docker container."""
        # Build test container
        container_id = await self._create_container(code_path)

        try:
            # Run pytest inside container
            result = await self._execute_tests(container_id)
            return result
        finally:
            # Cleanup container
            await self._cleanup_container(container_id)

    async def _create_container(self, code_path: Path) -> str:
        """Create isolated Docker container for testing."""
        # docker run with resource limits
        cmd = [
            'docker', 'run', '-d',
            '--memory', self.MEMORY_LIMIT,
            '--cpus', self.CPU_LIMIT,
            '--network', 'none',  # No network access
            '-v', f'{code_path}:/agent:ro',
            'agent-marketplace-test-runner:latest',
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    async def _execute_tests(self, container_id: str) -> TestResult:
        """Execute pytest in container."""
        cmd = [
            'docker', 'exec', container_id,
            'pytest', '/agent', '--json-report', '-q',
        ]

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.TIMEOUT_SECONDS,
            )
            stdout, stderr = await proc.communicate()
            return self._parse_pytest_output(stdout, stderr, proc.returncode)
        except asyncio.TimeoutError:
            return TestResult(
                passed=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                tests_skipped=0,
                duration_ms=self.TIMEOUT_SECONDS * 1000,
                output="Test execution timed out",
                coverage=None,
            )
```

---

## Validation Service

Orchestrates the full validation pipeline.

```python
# services/validation_service.py
from dataclasses import dataclass

@dataclass
class ValidationResult:
    passed: bool
    security: SecurityResult
    quality: QualityResult
    compatibility: CompatibilityResult
    tests: TestResult
    overall_score: float
    duration_ms: int

class ValidationService:
    """Orchestrates agent validation pipeline."""

    def __init__(
        self,
        scanner: SecurityScanner,
        quality_checker: QualityChecker,
        compatibility_checker: CompatibilityChecker,
        test_runner: TestRunner,
    ):
        self.scanner = scanner
        self.quality = quality_checker
        self.compatibility = compatibility_checker
        self.runner = test_runner

    async def validate_agent(self, code_path: Path) -> ValidationResult:
        """Run full validation pipeline."""
        start = time.monotonic()

        # Run all checks (some can run in parallel)
        security_result = await self.scanner.scan(code_path)

        # Only continue if security passes
        if not security_result.passed:
            return ValidationResult(
                passed=False,
                security=security_result,
                quality=None,
                compatibility=None,
                tests=None,
                overall_score=0.0,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # Run quality and compatibility in parallel
        quality_result, compat_result = await asyncio.gather(
            self.quality.check(code_path),
            self.compatibility.check(code_path),
        )

        # Only run tests if compatibility passes
        if compat_result.passed:
            test_result = await self.runner.run_tests(code_path)
        else:
            test_result = None

        # Calculate overall score
        overall = self._calculate_overall_score(
            security_result, quality_result, compat_result, test_result
        )

        return ValidationResult(
            passed=self._is_passing(security_result, quality_result, compat_result, test_result),
            security=security_result,
            quality=quality_result,
            compatibility=compat_result,
            tests=test_result,
            overall_score=overall,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    def _calculate_overall_score(self, *results) -> float:
        """Calculate weighted overall score."""
        # Weighted average of component scores
        pass

    def _is_passing(self, security, quality, compat, tests) -> bool:
        """Determine if agent passes validation."""
        return (
            security.passed and
            quality.passed and
            compat.passed and
            (tests is None or tests.passed)
        )
```

---

## Celery Integration

Background task processing for validation.

```python
# tasks/validation.py
from celery import shared_task
from agent_marketplace_api.validation import ValidationService

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def validate_agent_task(
    self,
    agent_version_id: int,
    storage_key: str,
) -> dict:
    """
    Background task to validate an agent submission.

    Args:
        agent_version_id: ID of the agent version to validate
        storage_key: S3 key where agent code is stored

    Returns:
        Validation result summary
    """
    try:
        # Download agent code from S3
        code_path = download_agent_code(storage_key)

        # Run validation (sync wrapper)
        result = run_validation_sync(code_path)

        # Store results in database
        store_validation_results(agent_version_id, result)

        # Update agent status
        if result.passed:
            mark_agent_validated(agent_version_id)
            move_to_permanent_storage(storage_key)
        else:
            mark_agent_failed(agent_version_id, result)

        return {
            'status': 'completed',
            'passed': result.passed,
            'score': result.overall_score,
        }

    except Exception as exc:
        # Retry on transient failures
        raise self.retry(exc=exc)

    finally:
        # Cleanup temporary files
        cleanup_temp_files(code_path)


def run_validation_sync(code_path: Path) -> ValidationResult:
    """Synchronous wrapper for async validation."""
    import asyncio

    service = get_validation_service()
    return asyncio.run(service.validate_agent(code_path))
```

---

## Celery Configuration

```python
# tasks/celery.py
from celery import Celery

celery_app = Celery(
    'agent_marketplace',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1',
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes hard limit
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_prefetch_multiplier=1,  # One task at a time
    task_routes={
        'tasks.validation.*': {'queue': 'validation'},
    },
)
```

---

## Database Storage

Validation results are stored for audit and display.

```sql
-- From DATABASE_SCHEMA.md
CREATE TABLE validation_results (
    id SERIAL PRIMARY KEY,
    agent_version_id INTEGER REFERENCES agent_versions(id) ON DELETE CASCADE,
    validator_type VARCHAR(50) NOT NULL,  -- security, quality, compatibility, tests
    passed BOOLEAN NOT NULL,
    details JSONB,  -- Full result details
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Example stored result:**
```json
{
  "validator_type": "security",
  "passed": true,
  "details": {
    "vulnerabilities": [],
    "warnings": ["Consider pinning dependency versions"],
    "scan_duration_ms": 1250
  }
}
```

---

## API Endpoints

### Check Validation Status

```
GET /api/v1/agents/{slug}/validation
```

**Response:**
```json
{
  "status": "completed",
  "passed": true,
  "started_at": "2025-01-10T10:00:00Z",
  "completed_at": "2025-01-10T10:02:30Z",
  "results": {
    "security": {
      "passed": true,
      "vulnerabilities": 0,
      "warnings": 1
    },
    "quality": {
      "passed": true,
      "score": 0.85,
      "lint_errors": 0,
      "type_errors": 2
    },
    "compatibility": {
      "passed": true,
      "pytest_agents_version": "0.5.0"
    },
    "tests": {
      "passed": true,
      "tests_run": 15,
      "tests_passed": 15,
      "coverage": 0.92
    }
  },
  "overall_score": 0.88
}
```

### Validation Status Values

| Status | Description |
|--------|-------------|
| `pending` | Queued, not yet started |
| `running` | Currently being validated |
| `completed` | Finished successfully |
| `failed` | Validation failed |
| `error` | System error during validation |

---

## Validation Flow Diagram

```
┌─────────────┐
│ Agent       │
│ Upload      │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│ Store in S3 │
│ (temporary) │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│ Queue       │
│ Celery Task │
└─────┬───────┘
      │
      ▼
┌─────────────┐     ┌─────────────┐
│ Security    │────▶│ FAIL: Stop  │
│ Scan        │     │ & Notify    │
└─────┬───────┘     └─────────────┘
      │ PASS
      ▼
┌─────────────┬─────────────┐
│ Quality     │ Compat      │  (parallel)
│ Check       │ Check       │
└─────┬───────┴──────┬──────┘
      │              │
      ▼              ▼
┌─────────────────────────┐
│ Both Pass?              │
└─────┬───────────────────┘
      │ YES
      ▼
┌─────────────┐
│ Run Tests   │
│ (Docker)    │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│ Store       │
│ Results     │
└─────┬───────┘
      │
      ▼
┌─────────────┐     ┌─────────────┐
│ All Pass?   │────▶│ Move to     │
│             │ YES │ Permanent   │
└─────┬───────┘     │ Storage     │
      │ NO          └─────────────┘
      ▼
┌─────────────┐
│ Mark Failed │
│ Notify User │
└─────────────┘
```

---

## Configuration

Environment variables for validation:

```bash
# Validation settings
VALIDATION_TIMEOUT_SECONDS=300
VALIDATION_MEMORY_LIMIT=512m
VALIDATION_CPU_LIMIT=1.0
VALIDATION_MIN_QUALITY_SCORE=0.7

# External tools
SNYK_TOKEN=your_snyk_token
SNYK_ORG=your_org

# Docker settings
VALIDATION_DOCKER_IMAGE=agent-marketplace-test-runner:latest
VALIDATION_DOCKER_NETWORK=none
```

---

## Security Considerations

1. **Sandboxed Execution**: All tests run in isolated Docker containers with no network access
2. **Resource Limits**: CPU and memory limits prevent resource exhaustion
3. **Timeout Enforcement**: Hard timeout prevents infinite loops
4. **No Persistence**: Containers are destroyed after validation
5. **Code Scanning**: Security scan runs BEFORE any code execution
6. **Dependency Auditing**: All dependencies checked against vulnerability databases

---

## Testing the Pipeline

```python
# tests/unit/test_validation.py
import pytest
from pathlib import Path
from agent_marketplace_api.validation import ValidationService

class TestValidationPipeline:
    """Tests for validation pipeline."""

    @pytest.fixture
    def sample_agent_path(self, tmp_path):
        """Create sample agent for testing."""
        agent_dir = tmp_path / "sample_agent"
        agent_dir.mkdir()

        # Create minimal agent
        (agent_dir / "agent.py").write_text('''
from pytest_agents import agent

@agent
class SampleAgent:
    """Sample agent for testing."""

    def run(self, task: str) -> str:
        return f"Completed: {task}"
''')

        (agent_dir / "requirements.txt").write_text("pytest-agents>=0.5.0\n")

        return agent_dir

    @pytest.mark.asyncio
    async def test_valid_agent_passes(self, sample_agent_path):
        """Test that valid agent passes validation."""
        service = ValidationService(...)
        result = await service.validate_agent(sample_agent_path)

        assert result.passed is True
        assert result.security.passed is True
        assert result.quality.passed is True
        assert result.compatibility.passed is True

    @pytest.mark.asyncio
    async def test_agent_with_security_issue_fails(self, tmp_path):
        """Test that agent with security issues fails."""
        agent_dir = tmp_path / "bad_agent"
        agent_dir.mkdir()

        # Agent with dangerous code
        (agent_dir / "agent.py").write_text('''
import os
os.system("rm -rf /")  # Dangerous!
''')

        service = ValidationService(...)
        result = await service.validate_agent(agent_dir)

        assert result.passed is False
        assert result.security.passed is False
        assert len(result.security.vulnerabilities) > 0
```

---

## Monitoring

Prometheus metrics for validation pipeline:

```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
validations_total = Counter(
    'validations_total',
    'Total validation runs',
    ['status']  # passed, failed, error
)

# Histograms
validation_duration = Histogram(
    'validation_duration_seconds',
    'Validation duration',
    buckets=[10, 30, 60, 120, 300, 600]
)

# Gauges
validations_pending = Gauge(
    'validations_pending',
    'Number of pending validations'
)
```

# Contributing to Agent Marketplace API

Thank you for your interest in contributing to Agent Marketplace API! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- uv (recommended) or pip
- Git

### Development Setup

1. Fork the repository on GitHub

2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/agent-marketplace-api.git
cd agent-marketplace-api
```

3. Add the upstream remote:
```bash
git remote add upstream https://github.com/kmcallorum/agent-marketplace-api.git
```

4. Start infrastructure services:
```bash
docker-compose up -d
```

5. Install dependencies:
```bash
uv sync
```

6. Run migrations:
```bash
uv run alembic upgrade head
```

7. Verify your setup:
```bash
uv run pytest
```

## Development Workflow

### Creating a Branch

Create a feature branch from `main`:
```bash
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-search-filters` - For new features
- `fix/agent-download-error` - For bug fixes
- `docs/update-api-docs` - For documentation
- `refactor/improve-validation` - For refactoring

### Making Changes

1. Write your code following the project's coding standards
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all quality checks pass

### Quality Checks

Before submitting, run all quality checks:

```bash
# Lint code
uv run ruff check src tests

# Fix auto-fixable issues
uv run ruff check src tests --fix

# Format code
uv run ruff format src tests

# Type checking
uv run mypy src

# Run tests with coverage
uv run pytest --cov --cov-fail-under=99
```

All checks must pass before your PR can be merged.

### Commit Messages

Write clear, descriptive commit messages:

```
<type>: <short description>

<optional longer description>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat: add agent search by category

fix: resolve download URL expiration issue

docs: update API endpoint documentation
```

### Submitting a Pull Request

1. Push your branch to your fork:
```bash
git push origin feature/your-feature-name
```

2. Create a Pull Request on GitHub

3. Fill out the PR template with:
   - Description of changes
   - Related issue numbers
   - Testing performed
   - Screenshots (if applicable)

4. Wait for CI checks to pass

5. Address review feedback

## Coding Standards

### Python Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Maximum line length: 88 characters (ruff default)
- Use meaningful variable and function names

### Code Organization

```python
# Standard library imports
from datetime import datetime
from typing import Any

# Third-party imports
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Local imports
from agent_marketplace_api.models import Agent
from agent_marketplace_api.schemas import AgentCreate
```

### Testing

- Write tests for all new functionality
- Maintain 99%+ code coverage
- Use descriptive test names
- Follow the Arrange-Act-Assert pattern

```python
class TestAgentService:
    """Tests for AgentService."""

    async def test_create_agent_success(self) -> None:
        """Test creating an agent successfully."""
        # Arrange
        data = AgentCreate(name="Test Agent", ...)

        # Act
        result = await service.create_agent(data, user)

        # Assert
        assert result.name == "Test Agent"
```

### Documentation

- Add docstrings to all public functions and classes
- Keep docstrings concise and informative
- Update README.md for user-facing changes
- Update API documentation for endpoint changes

## Project Structure

```
src/agent_marketplace_api/
├── api/           # API endpoints
├── core/          # Core utilities (metrics, etc.)
├── models/        # SQLAlchemy models
├── repositories/  # Data access layer
├── schemas/       # Pydantic schemas
├── services/      # Business logic
├── tasks/         # Background tasks
└── validation/    # Validation pipeline

tests/
├── unit/          # Unit tests
├── integration/   # Integration tests
└── conftest.py    # Test fixtures
```

## Reporting Issues

### Bug Reports

When reporting bugs, include:
- Python version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages/stack traces

### Feature Requests

For feature requests, describe:
- The problem you're trying to solve
- Your proposed solution
- Alternative approaches considered
- Impact on existing functionality

## Getting Help

- Open an issue for questions
- Check existing issues and PRs
- Review the documentation in `docs/`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

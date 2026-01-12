# Agent Marketplace API

[![PyPI](https://img.shields.io/pypi/v/agent-marketplace-ld-api)](https://pypi.org/project/agent-marketplace-ld-api/)
[![CI](https://github.com/kmcallorum/agent-marketplace-ld-api/actions/workflows/ci.yml/badge.svg)](https://github.com/kmcallorum/agent-marketplace-ld-api/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/kmcallorum/agent-marketplace-ld-api/branch/main/graph/badge.svg)](https://codecov.io/gh/kmcallorum/agent-marketplace-ld-api)
[![Snyk Security](https://snyk.io/test/github/kmcallorum/agent-marketplace-ld-api/badge.svg)](https://snyk.io/test/github/kmcallorum/agent-marketplace-ld-api)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type Checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue)](https://mypy-lang.org/)
[![pytest-agents](https://img.shields.io/badge/built%20for-pytest--agents-purple)](https://github.com/pytest-agents/pytest-agents)

FastAPI backend for Agent Marketplace - the central hub for discovering, publishing, and managing AI agents built with pytest-agents.

## Features

- **Agent Discovery** - Search and browse AI agents by category, rating, and popularity
- **Agent Publishing** - Upload, validate, and publish agents with version management
- **Validation Pipeline** - Automated security scanning and quality checks
- **Reviews & Ratings** - Community-driven feedback system
- **Analytics** - Track downloads, stars, and trending agents
- **GitHub OAuth** - Secure authentication via GitHub

## Tech Stack

- **Framework**: FastAPI 0.109+ with async/await
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Cache**: Redis
- **Background Tasks**: Celery
- **Storage**: S3/MinIO
- **Metrics**: Prometheus

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- uv (recommended) or pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/kmcallorum/agent-marketplace-ld-api.git
cd agent-marketplace-ld-api
```

2. Start infrastructure services:
```bash
docker-compose up -d
```

3. Install dependencies:
```bash
uv sync
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run database migrations:
```bash
uv run alembic upgrade head
```

6. Start the development server:
```bash
uv run uvicorn agent_marketplace_api.main:app --reload
```

The API will be available at http://localhost:8000

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Configuration

Configuration is managed via environment variables. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/agent_marketplace` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `S3_ENDPOINT` | S3/MinIO endpoint | `http://localhost:9000` |
| `S3_ACCESS_KEY` | S3 access key | - |
| `S3_SECRET_KEY` | S3 secret key | - |
| `S3_BUCKET` | S3 bucket name | `agents` |
| `JWT_SECRET_KEY` | Secret for JWT signing | - |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `GITHUB_CLIENT_ID` | GitHub OAuth client ID | - |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth client secret | - |

## API Endpoints

### Authentication
- `POST /api/v1/auth/github` - GitHub OAuth callback
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout user
- `GET /api/v1/auth/me` - Get current user

### Agents
- `GET /api/v1/agents` - List agents
- `POST /api/v1/agents` - Publish new agent
- `GET /api/v1/agents/{slug}` - Get agent details
- `PUT /api/v1/agents/{slug}` - Update agent
- `DELETE /api/v1/agents/{slug}` - Unpublish agent
- `GET /api/v1/agents/{slug}/versions` - Get version history
- `POST /api/v1/agents/{slug}/versions` - Publish new version
- `GET /api/v1/agents/{slug}/download/{version}` - Download agent
- `POST /api/v1/agents/{slug}/star` - Star agent
- `DELETE /api/v1/agents/{slug}/star` - Unstar agent

### Reviews
- `GET /api/v1/agents/{slug}/reviews` - List reviews
- `POST /api/v1/agents/{slug}/reviews` - Create review
- `PUT /api/v1/reviews/{id}` - Update review
- `DELETE /api/v1/reviews/{id}` - Delete review

### Search
- `GET /api/v1/search` - Global search
- `GET /api/v1/search/agents` - Search agents
- `GET /api/v1/search/suggestions` - Get suggestions

### Analytics
- `GET /api/v1/stats` - Platform statistics
- `GET /api/v1/trending` - Trending agents
- `GET /api/v1/popular` - Popular agents

### System
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_agent_service.py

# Run with verbose output
uv run pytest -v
```

### Code Quality

```bash
# Lint code
uv run ruff check src tests

# Fix linting issues
uv run ruff check src tests --fix

# Type checking
uv run mypy src

# Format code
uv run ruff format src tests
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "Description"

# Apply migrations
uv run alembic upgrade head

# Rollback one version
uv run alembic downgrade -1

# Show current version
uv run alembic current
```

## Docker

### Build Image

```bash
docker build -t agent-marketplace-api .
```

### Run with Docker Compose

```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# Stop services
docker-compose down
```

## Project Structure

```
src/agent_marketplace_api/
├── __init__.py
├── main.py              # FastAPI application
├── config.py            # Configuration settings
├── database.py          # Database setup
├── security.py          # JWT and password utilities
├── auth.py              # Authentication helpers
├── storage.py           # S3/MinIO client
├── api/
│   ├── deps.py          # Dependency injection
│   └── v1/
│       ├── agents.py    # Agent endpoints
│       ├── auth.py      # Auth endpoints
│       ├── reviews.py   # Review endpoints
│       ├── categories.py# Category endpoints
│       ├── users.py     # User endpoints
│       ├── search.py    # Search endpoints
│       └── analytics.py # Analytics endpoints
├── models/
│   ├── agent.py         # Agent model
│   ├── user.py          # User model
│   ├── review.py        # Review model
│   └── category.py      # Category model
├── schemas/
│   ├── agent.py         # Agent schemas
│   ├── user.py          # User schemas
│   ├── review.py        # Review schemas
│   ├── search.py        # Search schemas
│   └── analytics.py     # Analytics schemas
├── services/
│   ├── agent_service.py # Agent business logic
│   ├── review_service.py# Review business logic
│   ├── search_service.py# Search functionality
│   └── analytics_service.py # Analytics
├── repositories/
│   ├── base.py          # Base repository
│   ├── agent_repo.py    # Agent data access
│   └── review_repo.py   # Review data access
├── validation/
│   ├── scanner.py       # Security scanning
│   ├── quality.py       # Code quality
│   └── runner.py        # Test runner
├── tasks/
│   ├── celery.py        # Celery configuration
│   └── validation.py    # Background validation
└── core/
    └── metrics.py       # Prometheus metrics
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

See [SECURITY.md](SECURITY.md) for security policy and reporting vulnerabilities.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - SQL toolkit and ORM
- [pytest-agents](https://github.com/pytest-agents/pytest-agents) - Agent testing framework

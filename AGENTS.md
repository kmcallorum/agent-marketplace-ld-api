# agent-marketplace-api - BUILD GUIDE

## Project Overview

FastAPI backend for Agent Marketplace - the central hub for discovering, publishing, and managing AI agents built with pytest-agents.

**Goal:** Build incrementally in phases. Each phase is small enough for Claude Code to process without hitting rate limits.

---

## Tech Stack

**Core:**
- FastAPI 0.109+ with async/await
- PostgreSQL with SQLAlchemy 2.0 (async)
- Alembic for migrations
- Redis for caching
- Celery for background tasks
- S3/MinIO for file storage

**Dev:**
- pytest with 100% coverage requirement
- ruff for linting
- mypy strict mode
- Docker + docker-compose

---

## Build Phases

### Phase 1: Project Structure & Basic API
**Files to create:**
```
src/agent_marketplace_api/
├── __init__.py
├── main.py              # FastAPI app
├── config.py            # Settings (Pydantic)
├── database.py          # SQLAlchemy setup
└── py.typed

tests/
├── conftest.py
└── unit/
    └── test_config.py

pyproject.toml           # Dependencies
docker-compose.yml       # PostgreSQL, Redis, MinIO
.github/workflows/ci.yml # Basic CI
```

**Success criteria:**
- FastAPI app runs
- Can connect to PostgreSQL
- Basic CI passes

### Phase 2: Database Models & Schemas
**Files to create:**
```
src/agent_marketplace_api/
├── models/
│   ├── __init__.py
│   ├── agent.py         # Agent model
│   ├── user.py          # User model
│   ├── review.py        # Review model
│   └── category.py      # Category model
└── schemas/
    ├── __init__.py
    ├── agent.py         # Pydantic schemas
    ├── user.py
    └── review.py

migrations/              # Alembic migrations
alembic.ini
```

**Success criteria:**
- All models defined
- Migrations run successfully
- Schemas validate data

### Phase 3: Core API Endpoints (Agents)
**Files to create:**
```
src/agent_marketplace_api/
├── api/
│   └── v1/
│       ├── __init__.py
│       └── agents.py    # Agent CRUD endpoints
├── services/
│   ├── __init__.py
│   └── agent_service.py # Business logic
└── repositories/
    ├── __init__.py
    ├── base.py          # Base repository
    └── agent_repo.py    # Agent data access

tests/
├── unit/
│   ├── test_agent_service.py
│   └── test_agent_repo.py
└── integration/
    └── test_agent_api.py
```

**Success criteria:**
- GET /api/v1/agents works
- GET /api/v1/agents/{slug} works
- POST /api/v1/agents works
- 100% test coverage

### Phase 4: Authentication
**Files to create:**
```
src/agent_marketplace_api/
├── security.py          # JWT, password hashing
├── auth.py              # Auth utilities
├── api/v1/
│   └── auth.py          # Auth endpoints
└── dependencies.py      # FastAPI dependencies

tests/
├── unit/
│   └── test_security.py
└── integration/
    └── test_auth_flow.py
```

**Success criteria:**
- GitHub OAuth works
- JWT tokens issued
- Protected endpoints work
- Auth tests pass

### Phase 5: File Storage & Upload
**Files to create:**
```
src/agent_marketplace_api/
├── storage.py           # S3/MinIO client
└── api/v1/
    └── upload.py        # File upload endpoint

tests/
├── unit/
│   └── test_storage.py
└── integration/
    └── test_upload.py
```

**Success criteria:**
- Can upload files to S3/MinIO
- Can download files
- Presigned URLs work

### Phase 6: Validation Pipeline
**Files to create:**
```
src/agent_marketplace_api/
├── validation/
│   ├── __init__.py
│   ├── scanner.py       # Security scanning
│   ├── quality.py       # Code quality
│   └── runner.py        # Test runner
├── services/
│   └── validation_service.py
└── tasks/
    ├── __init__.py
    ├── celery.py        # Celery config
    └── validation.py    # Background validation

tests/
├── unit/
│   └── test_validation.py
└── integration/
    └── test_validation_flow.py
```

**Success criteria:**
- Validation pipeline works
- Celery tasks execute
- Validation results stored

### Phase 7: Reviews & Social Features
**Files to create:**
```
src/agent_marketplace_api/
├── api/v1/
│   └── reviews.py       # Review endpoints
└── services/
    └── review_service.py

tests/
├── unit/
│   └── test_review_service.py
└── integration/
    └── test_reviews_api.py
```

**Success criteria:**
- Can create reviews
- Can star agents
- Rating calculations work

### Phase 8: Search & Analytics
**Files to create:**
```
src/agent_marketplace_api/
├── api/v1/
│   ├── search.py        # Search endpoints
│   └── analytics.py     # Analytics endpoints
└── services/
    ├── search_service.py
    └── analytics_service.py

tests/
├── unit/
│   └── test_search.py
└── integration/
    └── test_search_api.py
```

**Success criteria:**
- Search works
- Trending algorithms work
- Analytics tracked

### Phase 9: Prometheus Metrics
**Files to create:**
```
src/agent_marketplace_api/
└── core/
    └── metrics.py       # Prometheus metrics

tests/
└── unit/
    └── test_metrics.py
```

**Success criteria:**
- Metrics exposed at /metrics
- All operations tracked

### Phase 10: Documentation & Polish
**Files to create:**
```
README.md
CONTRIBUTING.md
SECURITY.md
CHANGELOG.md
LICENSE
.github/
└── workflows/
    ├── security.yml
    ├── coverage.yml
    └── release.yml
```

**Success criteria:**
- README complete
- All badges working
- 100% coverage maintained
- Ready for PyPI

---

## Detailed Specifications

See `docs/` directory for comprehensive specs:

- **docs/ARCHITECTURE.md** - Full architecture details
- **docs/DATABASE_SCHEMA.md** - Complete SQL schema
- **docs/API_ENDPOINTS.md** - All endpoint specs
- **docs/VALIDATION_PIPELINE.md** - Validation flow details
- **docs/TESTING_STRATEGY.md** - Test patterns and mocks
- **docs/AUTHENTICATION.md** - Auth implementation
- **docs/DEPLOYMENT.md** - Docker, CI/CD, deployment

---

## Development Workflow

### For Each Phase:

1. **Read phase requirements** (above)
2. **Check docs/** for detailed specs (if needed)
3. **Implement files** listed in phase
4. **Write tests** (100% coverage required)
5. **Run quality checks:**
   ```bash
   ruff check src tests
   mypy src
   pytest --cov --cov-fail-under=100
   ```
6. **Move to next phase** when all checks pass

### Quality Gates (Every Phase):
- ✅ All tests pass
- ✅ 100% coverage maintained
- ✅ No ruff errors
- ✅ No mypy errors
- ✅ Docker builds successfully

---

## Key Architectural Principles

### Dependency Injection Everywhere
```python
# Services receive dependencies
class AgentService:
    def __init__(
        self,
        agent_repo: AgentRepository,
        storage: StorageService,
    ):
        self.repo = agent_repo
        self.storage = storage
```

### Repository Pattern for Data Access
```python
# Base repository with CRUD
class BaseRepository(Generic[T]):
    async def get(self, id: int) -> T | None: ...
    async def create(self, obj: T) -> T: ...

# Specific repositories extend base
class AgentRepository(BaseRepository[Agent]):
    async def find_by_slug(self, slug: str) -> Agent | None: ...
```

### Pydantic for Everything
```python
# Settings
class Settings(BaseSettings): ...

# Schemas
class AgentCreate(BaseModel): ...

# Response models
class AgentResponse(BaseModel): ...
```

### Factory Pattern for Testing
```python
# Mock data factory
class MockDataManager:
    def create_agent(self, **overrides) -> Agent: ...
    def create_user(self, **overrides) -> User: ...
```

---

## Quick Reference

### Database Connection String
```python
postgresql+asyncpg://user:pass@localhost:5432/agent_marketplace
```

### Running Locally
```bash
# Start services
docker-compose up -d

# Run migrations
alembic upgrade head

# Start API
uvicorn agent_marketplace_api.main:app --reload

# Run tests
pytest --cov
```

### Essential Commands
```bash
# Quality checks
ruff check src tests
mypy src
pytest --cov --cov-fail-under=100

# Build Docker
docker build -t agent-marketplace-api .

# Run full stack
docker-compose up
```

---

## Success Criteria (Full Project)

When all phases complete:

1. ✅ All API endpoints work
2. ✅ Agent upload/download/validation flow works
3. ✅ GitHub OAuth authentication works
4. ✅ Search and discovery work
5. ✅ Reviews and stars work
6. ✅ 100% test coverage
7. ✅ All CI checks pass
8. ✅ Docker compose starts full stack
9. ✅ README has clear setup instructions
10. ✅ API docs at /docs work

---

## Build Strategy

**Recommended approach:**
1. Tell Claude Code to build **one phase at a time**
2. After each phase, verify it works
3. Move to next phase
4. Reference `docs/` when Claude needs more detail

**Example prompt for Claude Code:**
> "Build Phase 1: Project Structure & Basic API. Reference docs/ARCHITECTURE.md for details."

---

## Repository Info

**Repository:** `github.com/kmcallorum/agent-marketplace-api`

**Description:**
> "FastAPI backend for Agent Marketplace - central registry for discovering, publishing, and managing AI agents built with pytest-agents."

**Topics:**
```
fastapi, api, backend, ai-agents, pytest-agents, marketplace,
postgresql, redis, celery, docker, python, async, sqlalchemy
```

---

**This simplified AGENTS.md is optimized for Claude Code's processing limits. Build one phase at a time!**

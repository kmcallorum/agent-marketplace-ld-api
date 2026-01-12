# Architecture

System design and component architecture for agent-marketplace-api.

## High-Level Architecture

```
┌─────────────────────────────────────────┐
│          Load Balancer / CDN             │
└─────────────┬───────────────────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼────┐        ┌─────▼───┐
│ API    │        │ API     │  ← Multiple instances
│ Server │        │ Server  │
└───┬────┘        └─────┬───┘
    │                   │
    └─────────┬─────────┘
              │
    ┌─────────┴─────────────┐
    │                       │
┌───▼──────┐        ┌───────▼────┐
│PostgreSQL│        │   Redis    │
│ Database │        │   Cache    │
└──────────┘        └────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼─────┐      ┌──────▼──────┐
│  Celery │      │   S3/MinIO  │
│ Workers │      │   Storage   │
└─────────┘      └─────────────┘
```

## Components

### FastAPI Application (`main.py`)
**Responsibilities:**
- HTTP request handling
- Route registration
- Middleware setup
- CORS configuration
- Exception handling
- Startup/shutdown events

**Key features:**
- Async request handling
- OpenAPI documentation at `/docs`
- Health check endpoint at `/health`
- Metrics endpoint at `/metrics`

### Configuration (`config.py`)
**Responsibilities:**
- Environment variable loading
- Settings validation
- Default values
- Secrets management

**Uses Pydantic BaseSettings:**
```python
class Settings(BaseSettings):
    database_url: str
    redis_url: str
    s3_endpoint: str
    jwt_secret_key: str
    # ... more settings
```

### Database Layer (`database.py`)
**Responsibilities:**
- SQLAlchemy engine setup
- Async session management
- Connection pooling
- Migration support

**Pattern:**
```python
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=20,
    max_overflow=10,
)

async_session_maker = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### Models (`models/`)
**Responsibilities:**
- SQLAlchemy ORM models
- Relationships between entities
- Database constraints
- Indexes

**Pattern:**
```python
class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    # ... fields
    
    # Relationships
    author = relationship("User", back_populates="agents")
    versions = relationship("AgentVersion")
```

### Schemas (`schemas/`)
**Responsibilities:**
- Pydantic models for validation
- Request/response schemas
- Data transformation
- Type safety

**Pattern:**
```python
class AgentCreate(BaseModel):
    name: str = Field(..., min_length=3)
    description: str = Field(..., min_length=10)
    category: str
    
class AgentResponse(BaseModel):
    id: int
    name: str
    slug: str
    # ... fields
    
    model_config = ConfigDict(from_attributes=True)
```

### Repositories (`repositories/`)
**Responsibilities:**
- Data access layer
- Database queries
- CRUD operations
- Transaction management

**Pattern:**
```python
class BaseRepository(Generic[T]):
    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model
    
    async def get(self, id: int) -> T | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

class AgentRepository(BaseRepository[Agent]):
    async def find_by_slug(self, slug: str) -> Agent | None:
        # Custom queries
        pass
```

### Services (`services/`)
**Responsibilities:**
- Business logic
- Cross-cutting concerns
- Orchestration
- Validation

**Pattern:**
```python
class AgentService:
    def __init__(
        self,
        agent_repo: AgentRepository,
        storage: StorageService,
        validator: ValidationService,
    ):
        self.repo = agent_repo
        self.storage = storage
        self.validator = validator
    
    async def create_agent(
        self,
        data: AgentCreate,
        user: User,
        code_file: UploadFile,
    ) -> Agent:
        # Business logic here
        pass
```

### API Endpoints (`api/v1/`)
**Responsibilities:**
- Route definitions
- Request validation
- Response formatting
- Dependency injection
- Auth checks

**Pattern:**
```python
@router.get("/agents")
async def list_agents(
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentsListResponse:
    agents = await agent_service.list_agents(
        category=category,
        limit=limit,
        offset=offset,
    )
    return AgentsListResponse(items=agents)
```

### Security (`security.py`, `auth.py`)
**Responsibilities:**
- JWT token creation/validation
- Password hashing
- OAuth flows
- Permission checks

**Components:**
- JWT encoding/decoding
- Password hashing (bcrypt)
- GitHub OAuth handler
- Current user dependency

### Storage Service (`storage.py`)
**Responsibilities:**
- S3/MinIO integration
- File upload/download
- Presigned URL generation
- Cleanup operations

**Pattern:**
```python
class StorageService:
    def __init__(self, s3_client: boto3.client):
        self.s3 = s3_client
    
    async def upload_agent(
        self,
        key: str,
        file_data: bytes,
    ) -> str:
        # Upload to S3
        pass
    
    def generate_download_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        # Presigned URL
        pass
```

### Validation Pipeline (`validation/`)
**Responsibilities:**
- Security scanning (Snyk)
- Code quality checks (ruff, mypy)
- Compatibility testing
- Test execution

**Components:**
- `scanner.py` - Security scanning
- `quality.py` - Code quality
- `compatibility.py` - pytest-agents compatibility
- `runner.py` - Test execution

**Flow:**
```python
class ValidationService:
    async def validate_agent(
        self,
        code_path: Path,
    ) -> ValidationResult:
        # 1. Security scan
        security_result = await self.scanner.scan(code_path)
        
        # 2. Quality check
        quality_result = await self.quality.check(code_path)
        
        # 3. Compatibility test
        compat_result = await self.compatibility.test(code_path)
        
        # 4. Run tests
        test_result = await self.runner.run_tests(code_path)
        
        return ValidationResult.from_checks([
            security_result,
            quality_result,
            compat_result,
            test_result,
        ])
```

### Background Tasks (`tasks/`)
**Responsibilities:**
- Celery task definitions
- Async job processing
- Scheduled tasks
- Retry logic

**Tasks:**
- `validate_agent_task` - Run validation pipeline
- `aggregate_analytics_task` - Calculate statistics
- `cleanup_old_data_task` - Clean up stale data

**Pattern:**
```python
@celery_app.task(bind=True, max_retries=3)
def validate_agent_task(
    self,
    agent_version_id: int,
    code_path: str,
) -> dict:
    try:
        result = run_validation_sync(code_path)
        update_validation_results(agent_version_id, result)
        return {'status': 'completed'}
    except Exception as e:
        raise self.retry(exc=e, countdown=60)
```

### Metrics (`core/metrics.py`)
**Responsibilities:**
- Prometheus metrics
- Performance tracking
- Business metrics
- Error tracking

**Metrics:**
- Counters (downloads, uploads, requests)
- Histograms (request duration, validation time)
- Gauges (active users, pending validations)

---

## Data Flow

### Agent Publication Flow
```
1. User uploads agent (POST /api/v1/agents)
   ↓
2. API validates request schema
   ↓
3. Store agent code in S3 (temporary)
   ↓
4. Create agent record in PostgreSQL
   ↓
5. Queue validation job (Celery)
   ↓
6. Return 202 Accepted to user
   ↓
[Background]
7. Celery worker picks up job
   ↓
8. Run validation pipeline
   ↓
9. Update validation results
   ↓
10. Move to permanent storage if passed
   ↓
11. Mark agent as validated
   ↓
12. Notify user (future: email/webhook)
```

### Agent Download Flow
```
1. User requests download (GET /api/v1/agents/{slug}/download)
   ↓
2. API validates user permissions
   ↓
3. Generate presigned S3 URL
   ↓
4. Record download event (analytics)
   ↓
5. Increment download counter
   ↓
6. Return redirect to presigned URL
   ↓
7. User downloads directly from S3
```

### Search Flow
```
1. User searches (GET /api/v1/search/agents?q=code)
   ↓
2. Check Redis cache for results
   ↓
3. If cache miss, query PostgreSQL
   ↓
4. Apply filters (category, rating)
   ↓
5. Sort results (relevance, downloads, stars)
   ↓
6. Paginate results
   ↓
7. Cache results in Redis (5 minutes)
   ↓
8. Return results to user
```

---

## Dependency Injection

### DI Container (`dependencies.py`)
```python
# Database session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

# Repositories
def get_agent_repo(
    db: AsyncSession = Depends(get_db)
) -> AgentRepository:
    return AgentRepository(db, Agent)

# Services
def get_agent_service(
    agent_repo: AgentRepository = Depends(get_agent_repo),
    storage: StorageService = Depends(get_storage_service),
) -> AgentService:
    return AgentService(agent_repo, storage)

# Current user
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Verify token and return user
    pass
```

### Usage in Endpoints
```python
@router.post("/agents")
async def create_agent(
    data: AgentCreate,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    agent = await agent_service.create_agent(data, current_user)
    return AgentResponse.from_orm(agent)
```

---

## Caching Strategy

### Redis Cache Layers

**1. API Response Caching**
- Cache GET requests
- TTL: 5 minutes for lists, 15 minutes for details
- Invalidate on updates

**2. Session Storage**
- JWT refresh tokens
- User sessions
- TTL: 7 days

**3. Rate Limiting**
- Per-user request counts
- Sliding window algorithm
- TTL: 1 hour

**4. Analytics Aggregation**
- Pre-computed statistics
- Updated hourly by Celery
- TTL: 1 hour

---

## Error Handling

### Exception Hierarchy
```python
class AgentMarketplaceError(Exception):
    """Base exception"""
    pass

class AgentNotFoundError(AgentMarketplaceError):
    status_code = 404

class AuthenticationError(AgentMarketplaceError):
    status_code = 401

class ValidationError(AgentMarketplaceError):
    status_code = 422
```

### Exception Handlers
```python
@app.exception_handler(AgentNotFoundError)
async def agent_not_found_handler(
    request: Request,
    exc: AgentNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "Agent not found", "detail": str(exc)},
    )
```

---

## Security

### Authentication Flow
```
1. User clicks "Login with GitHub"
   ↓
2. Redirect to GitHub OAuth
   ↓
3. User authorizes app
   ↓
4. GitHub redirects back with code
   ↓
5. API exchanges code for GitHub token
   ↓
6. Fetch user info from GitHub
   ↓
7. Create/update user in database
   ↓
8. Generate JWT access + refresh tokens
   ↓
9. Return tokens to frontend
```

### JWT Structure
```json
{
  "sub": "user_id",
  "username": "johndoe",
  "exp": 1609459200,
  "iat": 1609455600,
  "type": "access"
}
```

### Protected Endpoints
```python
@router.post("/agents")
async def create_agent(
    current_user: User = Depends(get_current_user),  # ← Auth required
):
    pass
```

---

## Monitoring

### Health Checks
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": await check_database(),
        "redis": await check_redis(),
        "storage": await check_storage(),
    }
```

### Prometheus Metrics Endpoint
```python
@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

### Logging
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "agent_created",
    agent_id=agent.id,
    user_id=user.id,
    slug=agent.slug,
)
```

---

## Scalability

### Horizontal Scaling
- Stateless API servers
- Load balancer distributes requests
- Shared PostgreSQL + Redis
- S3 for distributed storage

### Database Optimization
- Connection pooling
- Read replicas for analytics
- Indexes on frequent queries
- Pagination for large results

### Caching Strategy
- Redis for hot data
- CDN for static assets
- Presigned URLs for downloads

### Background Jobs
- Celery workers scale independently
- Priority queues for urgent tasks
- Retry with exponential backoff

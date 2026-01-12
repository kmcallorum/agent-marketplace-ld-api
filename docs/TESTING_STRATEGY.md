# Testing Strategy

Comprehensive testing approach for agent-marketplace-api achieving 100% coverage.

## Testing Philosophy

**Goals:**
- 100% line and branch coverage
- Fast test execution (<30 seconds)
- Isolated, deterministic tests
- Easy to understand and maintain

**Pyramid:**
```
     /\
    /  \   E2E (5%)
   /____\
  /      \  Integration (15%)
 /________\
/          \ Unit (80%)
```

---

## Test Structure

```
tests/
├── unit/              # Fast, isolated tests
│   ├── test_agent_service.py
│   ├── test_user_service.py
│   ├── test_repositories.py
│   ├── test_security.py
│   └── test_validation.py
├── integration/       # API endpoint tests
│   ├── test_agent_api.py
│   ├── test_auth_api.py
│   ├── test_review_api.py
│   └── test_search_api.py
├── fixtures/          # Test data
│   ├── sample_agents/
│   ├── mock_users.py
│   └── mock_data.py
└── conftest.py        # Shared fixtures
```

---

## Mock Data Generation

### Factory Pattern
```python
# tests/fixtures/mock_data.py
from faker import Faker
from agent_marketplace_api.models import Agent, User

class MockDataManager:
    """Central mock data generation."""
    
    def __init__(self, seed: int = 42):
        self.faker = Faker()
        Faker.seed(seed)
    
    def create_agent(self, **overrides) -> Agent:
        """Create mock agent with optional overrides."""
        defaults = {
            'name': self.faker.catch_phrase(),
            'slug': self.faker.slug(),
            'description': self.faker.text(),
            'author_id': self.faker.random_int(1, 100),
            'version': '1.0.0',
            'category': self.faker.random_element(['pm', 'research', 'testing']),
            'downloads': self.faker.random_int(0, 1000),
            'stars': self.faker.random_int(0, 100),
            'rating': round(self.faker.random.uniform(0, 5), 2),
        }
        return Agent(**{**defaults, **overrides})
    
    def create_user(self, **overrides) -> User:
        """Create mock user."""
        defaults = {
            'github_id': self.faker.random_int(1000, 9999),
            'username': self.faker.user_name(),
            'email': self.faker.email(),
            'reputation': self.faker.random_int(0, 1000),
        }
        return User(**{**defaults, **overrides})
    
    def create_batch_agents(self, count: int = 10) -> list[Agent]:
        """Create multiple agents."""
        return [self.create_agent() for _ in range(count)]
```

---

## Fixtures (conftest.py)

### Database Fixtures
```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.fixture
async def db_engine():
    """Test database engine (in-memory SQLite)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    """Test database session."""
    async_session_maker = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session
```

### Mock Services
```python
@pytest.fixture
def mock_storage():
    """Mock storage service."""
    storage = Mock(spec=StorageService)
    storage.upload_agent.return_value = "mock_storage_key"
    storage.download_agent.return_value = b"mock_agent_code"
    storage.generate_download_url.return_value = "https://s3.example.com/mock"
    return storage

@pytest.fixture
def mock_validator():
    """Mock validation service."""
    validator = Mock(spec=ValidationService)
    validator.validate_agent.return_value = ValidationResult(
        passed=True,
        checks=[
            CheckResult(name="security", passed=True),
            CheckResult(name="quality", passed=True),
        ],
    )
    return validator
```

### Mock Data
```python
@pytest.fixture
def mock_data_manager():
    """Mock data manager with consistent seed."""
    return MockDataManager(seed=42)

@pytest.fixture
def mock_agent(mock_data_manager):
    """Single mock agent."""
    return mock_data_manager.create_agent()

@pytest.fixture
def mock_user(mock_data_manager):
    """Single mock user."""
    return mock_data_manager.create_user()

@pytest.fixture
def mock_agents(mock_data_manager):
    """List of mock agents."""
    return mock_data_manager.create_batch_agents(count=10)
```

### HTTP Client
```python
@pytest.fixture
async def client(db_session):
    """Test HTTP client."""
    from httpx import AsyncClient
    from agent_marketplace_api.main import app
    
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()
```

---

## Unit Tests

### Repository Tests
```python
# tests/unit/test_agent_repo.py
import pytest
from agent_marketplace_api.repositories import AgentRepository

class TestAgentRepository:
    """Tests for AgentRepository."""
    
    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session, mock_agent):
        """Test getting agent by ID."""
        # Arrange
        db_session.add(mock_agent)
        await db_session.commit()
        
        repo = AgentRepository(db_session, Agent)
        
        # Act
        agent = await repo.get(mock_agent.id)
        
        # Assert
        assert agent is not None
        assert agent.id == mock_agent.id
        assert agent.name == mock_agent.name
    
    @pytest.mark.asyncio
    async def test_get_by_slug(self, db_session, mock_agent):
        """Test finding agent by slug."""
        # Arrange
        db_session.add(mock_agent)
        await db_session.commit()
        
        repo = AgentRepository(db_session, Agent)
        
        # Act
        agent = await repo.find_by_slug(mock_agent.slug)
        
        # Assert
        assert agent is not None
        assert agent.slug == mock_agent.slug
    
    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db_session):
        """Test getting nonexistent agent returns None."""
        repo = AgentRepository(db_session, Agent)
        
        agent = await repo.get(99999)
        
        assert agent is None
    
    @pytest.mark.asyncio
    async def test_create(self, db_session, mock_agent):
        """Test creating agent."""
        repo = AgentRepository(db_session, Agent)
        
        # Act
        created = await repo.create(mock_agent)
        
        # Assert
        assert created.id is not None
        
        # Verify in database
        fetched = await repo.get(created.id)
        assert fetched is not None
        assert fetched.name == mock_agent.name
```

### Service Tests
```python
# tests/unit/test_agent_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from agent_marketplace_api.services import AgentService

class TestAgentService:
    """Tests for AgentService."""
    
    @pytest.mark.asyncio
    async def test_create_agent_success(
        self,
        mock_agent,
        mock_user,
    ):
        """Test successful agent creation."""
        # Arrange
        mock_repo = Mock()
        mock_repo.find_by_slug = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(return_value=mock_agent)
        
        mock_storage = Mock()
        mock_storage.upload_agent = AsyncMock(return_value="storage_key")
        
        service = AgentService(
            agent_repo=mock_repo,
            storage=mock_storage,
        )
        
        # Act
        agent = await service.create_agent(
            name="Test Agent",
            description="Test description",
            author=mock_user,
            code_file=b"mock_code",
        )
        
        # Assert
        assert agent.name == "Test Agent"
        mock_storage.upload_agent.assert_called_once()
        mock_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_agent_duplicate_slug(self):
        """Test agent creation with duplicate slug."""
        # Arrange
        mock_repo = Mock()
        mock_repo.find_by_slug = AsyncMock(return_value=Mock())  # Slug exists
        
        service = AgentService(agent_repo=mock_repo)
        
        # Act & Assert
        with pytest.raises(AgentAlreadyExistsError):
            await service.create_agent(
                name="Test Agent",
                slug="test-agent",
                author=Mock(),
            )
```

### Security Tests
```python
# tests/unit/test_security.py
import pytest
from agent_marketplace_api.security import (
    create_access_token,
    verify_token,
    hash_password,
    verify_password,
)

class TestSecurity:
    """Tests for security functions."""
    
    def test_create_and_verify_token(self):
        """Test JWT token creation and verification."""
        # Create token
        token = create_access_token({"sub": "123"})
        
        # Verify token
        payload = verify_token(token)
        
        assert payload["sub"] == "123"
        assert "exp" in payload
    
    def test_verify_invalid_token(self):
        """Test invalid token raises error."""
        with pytest.raises(AuthenticationError):
            verify_token("invalid_token")
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "secure_password123"
        
        # Hash password
        hashed = hash_password(password)
        
        # Verify correct password
        assert verify_password(password, hashed) is True
        
        # Verify incorrect password
        assert verify_password("wrong_password", hashed) is False
```

---

## Integration Tests

### API Endpoint Tests
```python
# tests/integration/test_agent_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.integration
class TestAgentAPI:
    """Integration tests for agent endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_agents(self, client: AsyncClient):
        """Test listing agents."""
        response = await client.get("/api/v1/agents")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    
    @pytest.mark.asyncio
    async def test_get_agent(
        self,
        client: AsyncClient,
        db_session,
        mock_agent,
    ):
        """Test getting agent by slug."""
        # Setup: Create agent in database
        db_session.add(mock_agent)
        await db_session.commit()
        
        # Act
        response = await client.get(f"/api/v1/agents/{mock_agent.slug}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == mock_agent.slug
        assert data["name"] == mock_agent.name
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, client: AsyncClient):
        """Test getting nonexistent agent returns 404."""
        response = await client.get("/api/v1/agents/nonexistent")
        
        assert response.status_code == 404
        assert "error" in response.json()
    
    @pytest.mark.asyncio
    async def test_create_agent_authenticated(
        self,
        client: AsyncClient,
        auth_token: str,
    ):
        """Test creating agent as authenticated user."""
        # Act
        response = await client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"code": ("agent.zip", b"mock_code")},
            data={
                "name": "Test Agent",
                "description": "Test description",
                "category": "testing",
            },
        )
        
        # Assert
        assert response.status_code == 202  # Accepted
        data = response.json()
        assert data["slug"] == "test-agent"
        assert data["validation_status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_create_agent_unauthenticated(
        self,
        client: AsyncClient,
    ):
        """Test creating agent without authentication fails."""
        response = await client.post(
            "/api/v1/agents",
            data={"name": "Test Agent"},
        )
        
        assert response.status_code == 401
```

### Auth Flow Tests
```python
# tests/integration/test_auth_flow.py
import pytest
from httpx import AsyncClient

@pytest.mark.integration
class TestAuthFlow:
    """Integration tests for authentication flow."""
    
    @pytest.mark.asyncio
    async def test_github_oauth_success(
        self,
        client: AsyncClient,
        mock_github_api,
    ):
        """Test successful GitHub OAuth flow."""
        # Mock GitHub API responses
        mock_github_api.post("/login/oauth/access_token").mock(
            return_value={"access_token": "github_token"}
        )
        mock_github_api.get("/user").mock(
            return_value={
                "id": 12345,
                "login": "testuser",
                "email": "test@example.com",
            }
        )
        
        # Act: Exchange GitHub code for tokens
        response = await client.post(
            "/api/v1/auth/github",
            json={"code": "github_auth_code"},
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_requires_auth(
        self,
        client: AsyncClient,
    ):
        """Test protected endpoint requires authentication."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(
        self,
        client: AsyncClient,
        auth_token: str,
    ):
        """Test protected endpoint with valid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "username" in data
```

---

## Coverage Enforcement

### pytest Configuration
```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --cov=src/agent_marketplace_api
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=100
    --strict-markers
    --disable-warnings
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
```

### Running Tests
```bash
# All tests with coverage
pytest --cov --cov-report=term-missing

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Specific test file
pytest tests/unit/test_agent_service.py

# Specific test
pytest tests/unit/test_agent_service.py::TestAgentService::test_create_agent_success

# Coverage report
pytest --cov --cov-report=html
# Opens htmlcov/index.html
```

---

## Testing Best Practices

### DO: Test One Thing
```python
# GOOD: Tests one specific behavior
def test_create_agent_with_duplicate_slug_raises_error():
    # Test only duplicate slug error
    pass

# BAD: Tests multiple things
def test_create_agent():
    # Tests creation, validation, storage, all in one
    pass
```

### DO: Use Descriptive Names
```python
# GOOD: Clear what it tests
def test_get_agent_by_slug_returns_agent_when_exists():
    pass

# BAD: Vague
def test_get_agent():
    pass
```

### DO: Arrange-Act-Assert Pattern
```python
def test_example():
    # Arrange: Setup
    agent = create_mock_agent()
    repo = AgentRepository(db)
    
    # Act: Execute
    result = await repo.create(agent)
    
    # Assert: Verify
    assert result.id is not None
```

### DON'T: Test Implementation Details
```python
# BAD: Tests internal method
def test_agent_service_calls_repo_get():
    service.create_agent(...)
    assert mock_repo.get.called  # Too specific

# GOOD: Tests behavior
def test_agent_service_creates_agent():
    agent = service.create_agent(...)
    assert agent.id is not None  # Behavior
```

---

## Mocking Guidelines

### When to Mock
- External services (S3, GitHub API)
- Database in unit tests
- Time-dependent functions
- Network calls

### When NOT to Mock
- Integration tests (use real database)
- Simple data structures
- Pure functions

### Mock Example
```python
from unittest.mock import Mock, AsyncMock, patch

# Mock async function
mock_fn = AsyncMock(return_value="result")
await mock_fn()  # Returns "result"

# Mock with side effect
mock_fn.side_effect = Exception("Error")

# Mock class
mock_service = Mock(spec=AgentService)
mock_service.create_agent = AsyncMock(return_value=agent)

# Patch decorator
@patch('agent_marketplace_api.services.storage')
def test_with_patched_storage(mock_storage):
    pass
```

---

## CI Integration

### GitHub Actions
```yaml
# .github/workflows/ci.yml
- name: Run tests with coverage
  run: |
    pytest --cov --cov-report=xml --cov-report=term
  
- name: Check 100% coverage
  run: |
    coverage report --fail-under=100
  
- name: Upload to Codecov
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: ./coverage.xml
    fail_ci_if_error: true
```

---

## Coverage Requirements

**100% line coverage is mandatory.**

If a line cannot be tested:
1. **Refactor** to make it testable
2. **Mark with pragma** only if absolutely necessary:
   ```python
   def unreachable_code():  # pragma: no cover
       # System-level error that can't be simulated
       pass
   ```

**Valid pragma use:**
- System-level errors (OOM, kernel panic)
- Defensive code that should never execute
- Platform-specific code (Windows-only on Linux CI)

**Invalid pragma use:**
- Hard-to-test code (refactor instead)
- External API calls (mock them)
- Database queries (use test DB)

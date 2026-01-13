# Deployment

Docker, CI/CD, and production deployment for agent-marketplace-api.

## Local Development

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- uv (Python package manager)

### Quick Start

```bash
# Clone repository
git clone https://github.com/kmcallorum/agent-marketplace-api.git
cd agent-marketplace-api

# Start infrastructure services
docker-compose up -d postgres redis minio

# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn agent_marketplace_api.main:app --reload

# API available at http://localhost:8000
# Docs available at http://localhost:8000/docs
```

---

## Docker Configuration

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./

# Install project
RUN uv sync --frozen --no-dev

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uv", "run", "uvicorn", "agent_marketplace_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile for Celery Worker

```dockerfile
# Dockerfile.worker
FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev

RUN useradd --create-home --shell /bin/bash app
USER app

CMD ["uv", "run", "celery", "-A", "agent_marketplace_api.tasks.celery", "worker", "--loglevel=info"]
```

---

## Docker Compose

### Development

```yaml
# docker-compose.yml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/agent_marketplace
      - REDIS_URL=redis://redis:6379/0
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=minioadmin
      - S3_SECRET_KEY=minioadmin
      - S3_BUCKET=agents
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-dev-secret-key-change-in-production}
      - GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}
      - GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_started
    volumes:
      - ./src:/app/src:ro  # For development hot-reload
    command: uv run uvicorn agent_marketplace_api.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/agent_marketplace
      - REDIS_URL=redis://redis:6379/0
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=minioadmin
      - S3_SECRET_KEY=minioadmin
      - S3_BUCKET=agents
    depends_on:
      - postgres
      - redis
      - minio

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=agent_marketplace
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"

  # Create default bucket on startup
  minio-setup:
    image: minio/mc:latest
    depends_on:
      - minio
    entrypoint: >
      /bin/sh -c "
      sleep 5;
      mc alias set local http://minio:9000 minioadmin minioadmin;
      mc mb local/agents --ignore-existing;
      exit 0;
      "

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### Production

```yaml
# docker-compose.prod.yml
services:
  api:
    image: ghcr.io/kmcallorum/agent-marketplace-api:latest
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          cpus: "0.5"
          memory: 256M
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - S3_ENDPOINT=${S3_ENDPOINT}
      - S3_ACCESS_KEY=${S3_ACCESS_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
      - S3_BUCKET=${S3_BUCKET}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}
      - GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  worker:
    image: ghcr.io/kmcallorum/agent-marketplace-api:latest
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "2.0"
          memory: 1G
    command: celery -A agent_marketplace_api.tasks.celery worker --loglevel=info
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - S3_ENDPOINT=${S3_ENDPOINT}
      - S3_ACCESS_KEY=${S3_ACCESS_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
```

---

## CI/CD with GitHub Actions

### Main CI Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: uv sync --dev

      - name: Run ruff check
        run: uv run ruff check src tests

      - name: Run ruff format check
        run: uv run ruff format --check src tests

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: uv sync --dev

      - name: Run mypy
        run: uv run mypy src

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: uv sync --dev

      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET_KEY: test-secret-key
        run: |
          uv run pytest --cov --cov-report=xml --cov-report=term --cov-fail-under=100

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: ./coverage.xml
          fail_ci_if_error: true

  build:
    runs-on: ubuntu-latest
    needs: [lint, typecheck, test]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: agent-marketplace-api:test
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Security Scanning

```yaml
# .github/workflows/security.yml
name: Security

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 0 * * *"  # Daily

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --dev

      - name: Run safety check
        run: uv run safety check

      - name: Run bandit
        run: uv run bandit -r src -ll

  container-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t agent-marketplace-api:scan .

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: agent-marketplace-api:scan
          format: table
          exit-code: 1
          severity: CRITICAL,HIGH
```

### Release Pipeline

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
```

---

## Environment Variables

### Required Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# Redis
REDIS_URL=redis://host:6379/0

# S3/MinIO Storage
S3_ENDPOINT=https://s3.amazonaws.com  # or http://minio:9000
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET=agents
S3_REGION=us-east-1

# Authentication
JWT_SECRET_KEY=your-super-secret-key-minimum-32-chars
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

### Optional Variables

```bash
# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
DEBUG=false
LOG_LEVEL=INFO

# Database Pool
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# JWT Settings
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100

# Validation
VALIDATION_TIMEOUT_SECONDS=300
VALIDATION_MEMORY_LIMIT=512m
```

---

## Production Deployment

### Kubernetes (Example)

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-marketplace-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agent-marketplace-api
  template:
    metadata:
      labels:
        app: agent-marketplace-api
    spec:
      containers:
        - name: api
          image: ghcr.io/kmcallorum/agent-marketplace-api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: agent-marketplace-secrets
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: agent-marketplace-api
spec:
  selector:
    app: agent-marketplace-api
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-marketplace-api
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - api.agent-marketplace.com
      secretName: agent-marketplace-tls
  rules:
    - host: api.agent-marketplace.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: agent-marketplace-api
                port:
                  number: 80
```

### Health Check Endpoint

```python
# main.py
@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint for load balancers."""
    checks = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"
        checks["status"] = "degraded"

    # Check Redis
    try:
        await redis_client.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)
```

---

## Database Migrations

### Running Migrations

```bash
# Create new migration
uv run alembic revision --autogenerate -m "Description of change"

# Apply all migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# Show current version
uv run alembic current

# Show migration history
uv run alembic history
```

### Production Migration Strategy

```bash
# In production, run migrations before deploying new code
# Option 1: Init container in Kubernetes
# Option 2: Separate migration job
# Option 3: Run in CI/CD before deployment

# Example: Migration job in CI
- name: Run migrations
  run: |
    uv run alembic upgrade head
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

---

## Monitoring

### Prometheus Metrics

```python
# Metrics exposed at /metrics endpoint
from prometheus_client import Counter, Histogram, generate_latest

requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain",
    )
```

### Logging

```python
# Structured logging with structlog
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()

# Usage
logger.info("agent_created", agent_id=123, user_id=456)
```

---

## Checklist

### Before First Deploy

- [ ] Set strong JWT_SECRET_KEY (32+ random chars)
- [ ] Configure GitHub OAuth app
- [ ] Set up PostgreSQL with proper credentials
- [ ] Set up Redis
- [ ] Set up S3/MinIO bucket
- [ ] Configure domain and SSL
- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Set up log aggregation
- [ ] Configure backup for database
- [ ] Set up alerting

### For Each Release

- [ ] All tests pass
- [ ] 100% coverage maintained
- [ ] No security vulnerabilities
- [ ] Database migrations ready
- [ ] Docker image builds successfully
- [ ] Health checks working
- [ ] Rollback plan documented

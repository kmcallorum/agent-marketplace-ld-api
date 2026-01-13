# Tutorial: Deploying with Docker

Step-by-step guide to deploy Agent Marketplace API using Docker and Docker Compose.

## Prerequisites

- Docker Engine 24.0+
- Docker Compose v2.20+
- 2GB RAM minimum
- Domain name (optional, for production)

## Step 1: Install Docker

### Ubuntu/Debian

```bash
# Remove old versions
sudo apt remove docker docker-engine docker.io containerd runc

# Install prerequisites
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

### macOS

Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/).

### Windows

Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/) with WSL 2 backend.

---

## Step 2: Clone the Repository

```bash
git clone https://github.com/kmcallorum/agent-marketplace-ld-api.git
cd agent-marketplace-ld-api
```

---

## Step 3: Configure Environment

### 3.1 Create Environment File

```bash
cp .env.example .env
```

### 3.2 Edit Configuration

```bash
nano .env
```

Set your values:

```bash
# Database (Docker internal network)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/agent_marketplace

# Redis
REDIS_URL=redis://redis:6379/0

# S3/MinIO
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=changeme_minio_secret
S3_BUCKET=agents

# JWT - Generate: openssl rand -hex 32
JWT_SECRET_KEY=your_secure_jwt_secret_at_least_32_characters
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/auth/github/callback

# API Settings
DEBUG=false
LOG_LEVEL=INFO
```

---

## Step 4: Development Deployment

### 4.1 Start All Services

```bash
docker compose up -d
```

This starts:
- **api**: FastAPI application on port 8000
- **worker**: Celery worker for background tasks
- **postgres**: PostgreSQL database on port 5432
- **redis**: Redis cache on port 6379
- **minio**: MinIO object storage on ports 9000 (API) and 9001 (console)

### 4.2 Run Database Migrations

```bash
docker compose exec api uv run alembic upgrade head
```

### 4.3 Verify Deployment

```bash
# Check all containers are running
docker compose ps

# Check API health
curl http://localhost:8000/health

# View logs
docker compose logs -f api
```

### 4.4 Access Points

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |
| MinIO Console | http://localhost:9001 |
| Health Check | http://localhost:8000/health |
| Metrics | http://localhost:8000/metrics |

---

## Step 5: Production Deployment

### 5.1 Create Production Compose File

```bash
nano docker-compose.prod.yml
```

```yaml
services:
  api:
    image: ghcr.io/kmcallorum/agent-marketplace-ld-api:latest
    # Or build locally:
    # build:
    #   context: .
    #   dockerfile: Dockerfile
    ports:
      - "8000:8000"
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
      - DEBUG=false
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: always
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          cpus: "0.5"
          memory: 256M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  worker:
    image: ghcr.io/kmcallorum/agent-marketplace-ld-api:latest
    command: uv run celery -A agent_marketplace_api.tasks.celery worker --loglevel=info
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - S3_ENDPOINT=${S3_ENDPOINT}
      - S3_ACCESS_KEY=${S3_ACCESS_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
      - S3_BUCKET=${S3_BUCKET}
    depends_on:
      - postgres
      - redis
    restart: always
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-postgres}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
      - POSTGRES_DB=${POSTGRES_DB:-agent_marketplace}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=${S3_ACCESS_KEY}
      - MINIO_ROOT_PASSWORD=${S3_SECRET_KEY}
    volumes:
      - minio_data:/data
    restart: always
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M

  minio-setup:
    image: minio/mc:latest
    depends_on:
      - minio
    entrypoint: >
      /bin/sh -c "
      sleep 10;
      mc alias set local http://minio:9000 ${S3_ACCESS_KEY} ${S3_SECRET_KEY};
      mc mb local/${S3_BUCKET} --ignore-existing;
      exit 0;
      "

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: always

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### 5.2 Create Nginx Configuration

```bash
nano nginx.conf
```

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
        keepalive 32;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        listen 80;
        server_name your-domain.com;

        # Redirect to HTTPS
        location / {
            return 301 https://$server_name$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
        ssl_prefer_server_ciphers off;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # API proxy
        location / {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";

            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Health check (no rate limit)
        location /health {
            proxy_pass http://api/health;
            proxy_http_version 1.1;
        }

        # File upload limit
        client_max_body_size 50M;
    }
}
```

### 5.3 Deploy Production Stack

```bash
# Build and start
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose -f docker-compose.prod.yml exec api uv run alembic upgrade head

# Verify
docker compose -f docker-compose.prod.yml ps
curl https://your-domain.com/health
```

---

## Step 6: Scaling

### 6.1 Scale API Instances

```bash
# Scale to 3 API instances
docker compose -f docker-compose.prod.yml up -d --scale api=3
```

Update nginx.conf upstream:

```nginx
upstream api {
    least_conn;
    server api:8000;
    keepalive 32;
}
```

### 6.2 Scale Workers

```bash
# Scale to 2 worker instances
docker compose -f docker-compose.prod.yml up -d --scale worker=2
```

---

## Step 7: Monitoring

### 7.1 Add Prometheus and Grafana

Create `docker-compose.monitoring.yml`:

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: always

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    restart: always

volumes:
  prometheus_data:
  grafana_data:
```

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'agent-marketplace-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics
```

Deploy monitoring:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
```

---

## Step 8: Backup and Restore

### 8.1 Backup Database

```bash
# Create backup
docker compose exec postgres pg_dump -U postgres agent_marketplace | gzip > backup_$(date +%Y%m%d).sql.gz

# Automated backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR
docker compose exec -T postgres pg_dump -U postgres agent_marketplace | gzip > $BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql.gz
find $BACKUP_DIR -mtime +7 -delete
EOF
chmod +x backup.sh
```

### 8.2 Restore Database

```bash
# Stop API to prevent new connections
docker compose stop api worker

# Restore
gunzip -c backup_20250113.sql.gz | docker compose exec -T postgres psql -U postgres agent_marketplace

# Start API
docker compose start api worker
```

### 8.3 Backup MinIO Data

```bash
# Backup
docker compose exec minio mc mirror /data ./minio_backup

# Or use volume backup
docker run --rm -v agent-marketplace-ld-api_minio_data:/data -v $(pwd):/backup alpine tar czf /backup/minio_backup.tar.gz /data
```

---

## Step 9: Updates and Maintenance

### 9.1 Update Application

```bash
# Pull latest image
docker compose pull

# Or rebuild from source
git pull origin main
docker compose build --no-cache

# Apply update with zero downtime
docker compose up -d --no-deps api

# Run migrations if needed
docker compose exec api uv run alembic upgrade head
```

### 9.2 View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api

# Since specific time
docker compose logs --since="2025-01-13T10:00:00" api
```

### 9.3 Shell Access

```bash
# API container
docker compose exec api bash

# PostgreSQL
docker compose exec postgres psql -U postgres agent_marketplace

# Redis
docker compose exec redis redis-cli
```

---

## Step 10: Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs api

# Check container status
docker compose ps -a

# Inspect container
docker inspect $(docker compose ps -q api)
```

### Database Connection Issues

```bash
# Check if postgres is healthy
docker compose exec postgres pg_isready

# Check network connectivity
docker compose exec api ping postgres

# Verify DATABASE_URL
docker compose exec api env | grep DATABASE
```

### Out of Disk Space

```bash
# Check disk usage
docker system df

# Clean up unused resources
docker system prune -a --volumes

# Remove old images
docker image prune -a
```

### Memory Issues

```bash
# Check container memory usage
docker stats

# Adjust limits in compose file
deploy:
  resources:
    limits:
      memory: 1G
```

---

## Docker Commands Reference

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v

# Restart specific service
docker compose restart api

# Rebuild and restart
docker compose up -d --build api

# View running containers
docker compose ps

# Execute command in container
docker compose exec api uv run alembic upgrade head

# View logs
docker compose logs -f api

# Scale service
docker compose up -d --scale api=3

# Pull latest images
docker compose pull
```

---

## Summary

You now have Agent Marketplace API running with Docker:

- FastAPI application
- Celery worker for background tasks
- PostgreSQL database with persistent storage
- Redis cache
- MinIO object storage
- Nginx reverse proxy (production)
- Optional Prometheus + Grafana monitoring

For production deployments, remember to:
- Use strong passwords for all services
- Enable SSL/TLS
- Set up regular backups
- Configure monitoring and alerting
- Use external managed databases for critical workloads

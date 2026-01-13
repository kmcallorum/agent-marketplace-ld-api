# Tutorial: Deploying on a Linux VM

Step-by-step guide to deploy Agent Marketplace API on a Linux virtual machine (Ubuntu/Debian).

## Prerequisites

- Linux VM (Ubuntu 22.04 LTS recommended)
- Minimum 2 vCPU, 4GB RAM, 20GB storage
- Root or sudo access
- Domain name (optional, for SSL)

## Step 1: Initial Server Setup

### 1.1 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Required Packages

```bash
sudo apt install -y \
    curl \
    git \
    build-essential \
    libpq-dev \
    nginx \
    certbot \
    python3-certbot-nginx
```

### 1.3 Create Application User

```bash
sudo useradd -m -s /bin/bash agentapi
sudo usermod -aG sudo agentapi
```

---

## Step 2: Install Python 3.11+

### 2.1 Add Deadsnakes PPA (Ubuntu)

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

### 2.2 Install uv Package Manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

Verify installation:

```bash
uv --version
python3.11 --version
```

---

## Step 3: Install PostgreSQL

### 3.1 Install PostgreSQL 16

```bash
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update
sudo apt install -y postgresql-16
```

### 3.2 Create Database and User

```bash
sudo -u postgres psql << EOF
CREATE USER agentapi WITH PASSWORD 'your_secure_password';
CREATE DATABASE agent_marketplace OWNER agentapi;
GRANT ALL PRIVILEGES ON DATABASE agent_marketplace TO agentapi;
EOF
```

### 3.3 Configure PostgreSQL for Local Connections

Edit `/etc/postgresql/16/main/pg_hba.conf`:

```bash
sudo nano /etc/postgresql/16/main/pg_hba.conf
```

Add this line:

```
local   agent_marketplace   agentapi                                md5
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

---

## Step 4: Install Redis

```bash
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

Verify Redis is running:

```bash
redis-cli ping
# Should return: PONG
```

---

## Step 5: Install MinIO (S3-compatible Storage)

### 5.1 Download and Install MinIO

```bash
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
sudo mv minio /usr/local/bin/
```

### 5.2 Create MinIO User and Directories

```bash
sudo useradd -r minio-user -s /sbin/nologin
sudo mkdir -p /data/minio
sudo chown minio-user:minio-user /data/minio
```

### 5.3 Create MinIO Environment File

```bash
sudo nano /etc/default/minio
```

Add:

```bash
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password
MINIO_VOLUMES="/data/minio"
MINIO_OPTS="--console-address :9001"
```

### 5.4 Create Systemd Service

```bash
sudo nano /etc/systemd/system/minio.service
```

Add:

```ini
[Unit]
Description=MinIO
Documentation=https://docs.min.io
Wants=network-online.target
After=network-online.target

[Service]
User=minio-user
Group=minio-user
EnvironmentFile=/etc/default/minio
ExecStart=/usr/local/bin/minio server $MINIO_OPTS $MINIO_VOLUMES
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

### 5.5 Start MinIO

```bash
sudo systemctl daemon-reload
sudo systemctl enable minio
sudo systemctl start minio
```

### 5.6 Create Bucket

```bash
# Install MinIO client
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# Configure and create bucket
mc alias set local http://localhost:9000 minioadmin your_minio_password
mc mb local/agents
```

---

## Step 6: Deploy Application

### 6.1 Switch to Application User

```bash
sudo su - agentapi
```

### 6.2 Clone Repository

```bash
git clone https://github.com/kmcallorum/agent-marketplace-ld-api.git
cd agent-marketplace-ld-api
```

### 6.3 Install Dependencies

```bash
uv sync --no-dev
```

### 6.4 Create Environment File

```bash
nano .env
```

Add your configuration:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://agentapi:your_secure_password@localhost:5432/agent_marketplace

# Redis
REDIS_URL=redis://localhost:6379/0

# S3/MinIO
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=your_minio_password
S3_BUCKET=agents

# JWT - Generate a secure key: openssl rand -hex 32
JWT_SECRET_KEY=your_generated_secret_key_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=https://your-domain.com/api/v1/auth/github/callback

# API Settings
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=false
LOG_LEVEL=INFO
```

### 6.5 Run Database Migrations

```bash
uv run alembic upgrade head
```

### 6.6 Test Application

```bash
uv run uvicorn agent_marketplace_api.main:app --host 127.0.0.1 --port 8000
```

Visit `http://your-server-ip:8000/health` to verify. Press `Ctrl+C` to stop.

---

## Step 7: Configure Systemd Service

### 7.1 Create API Service

```bash
sudo nano /etc/systemd/system/agentapi.service
```

Add:

```ini
[Unit]
Description=Agent Marketplace API
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=agentapi
Group=agentapi
WorkingDirectory=/home/agentapi/agent-marketplace-ld-api
Environment="PATH=/home/agentapi/.local/bin:/usr/bin"
EnvironmentFile=/home/agentapi/agent-marketplace-ld-api/.env
ExecStart=/home/agentapi/.local/bin/uv run uvicorn agent_marketplace_api.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 7.2 Create Celery Worker Service

```bash
sudo nano /etc/systemd/system/agentapi-worker.service
```

Add:

```ini
[Unit]
Description=Agent Marketplace Celery Worker
After=network.target redis.service

[Service]
Type=exec
User=agentapi
Group=agentapi
WorkingDirectory=/home/agentapi/agent-marketplace-ld-api
Environment="PATH=/home/agentapi/.local/bin:/usr/bin"
EnvironmentFile=/home/agentapi/agent-marketplace-ld-api/.env
ExecStart=/home/agentapi/.local/bin/uv run celery -A agent_marketplace_api.tasks.celery worker --loglevel=info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 7.3 Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable agentapi agentapi-worker
sudo systemctl start agentapi agentapi-worker
```

### 7.4 Check Status

```bash
sudo systemctl status agentapi
sudo systemctl status agentapi-worker
```

---

## Step 8: Configure Nginx Reverse Proxy

### 8.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/agentapi
```

Add:

```nginx
upstream agentapi {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS (uncomment after SSL setup)
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://agentapi;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://agentapi/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # File upload size limit
    client_max_body_size 50M;
}
```

### 8.2 Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/agentapi /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 9: Configure SSL with Let's Encrypt

### 9.1 Obtain SSL Certificate

```bash
sudo certbot --nginx -d your-domain.com
```

Follow the prompts. Certbot will automatically configure Nginx for HTTPS.

### 9.2 Auto-Renewal

Certbot sets up auto-renewal automatically. Test it:

```bash
sudo certbot renew --dry-run
```

---

## Step 10: Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'

# Enable firewall
sudo ufw enable

# Verify
sudo ufw status
```

---

## Step 11: Monitoring and Logs

### 11.1 View Application Logs

```bash
# API logs
sudo journalctl -u agentapi -f

# Worker logs
sudo journalctl -u agentapi-worker -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### 11.2 Check Service Health

```bash
# Check all services
sudo systemctl status agentapi agentapi-worker postgresql redis-server minio nginx

# Health endpoint
curl http://localhost:8000/health
```

---

## Step 12: Updating the Application

```bash
# Switch to application user
sudo su - agentapi
cd agent-marketplace-ld-api

# Pull latest changes
git pull origin main

# Update dependencies
uv sync --no-dev

# Run migrations
uv run alembic upgrade head

# Restart services
sudo systemctl restart agentapi agentapi-worker
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check logs
sudo journalctl -u agentapi -n 50

# Verify environment file
cat /home/agentapi/agent-marketplace-ld-api/.env

# Test manually
sudo su - agentapi
cd agent-marketplace-ld-api
uv run uvicorn agent_marketplace_api.main:app --host 127.0.0.1 --port 8000
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U agentapi -d agent_marketplace -h localhost

# Check pg_hba.conf
sudo cat /etc/postgresql/16/main/pg_hba.conf
```

### Redis Connection Issues

```bash
# Check Redis is running
sudo systemctl status redis-server

# Test connection
redis-cli ping
```

### Nginx 502 Bad Gateway

```bash
# Check if API is running
curl http://127.0.0.1:8000/health

# Check Nginx config
sudo nginx -t

# Restart services
sudo systemctl restart agentapi nginx
```

---

## Security Hardening

### 1. SSH Key Authentication Only

```bash
# Disable password authentication
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

### 2. Fail2Ban for Brute Force Protection

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3. Regular Updates

```bash
# Enable automatic security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 4. Backup Database

```bash
# Create backup script
sudo nano /home/agentapi/backup.sh
```

Add:

```bash
#!/bin/bash
BACKUP_DIR="/home/agentapi/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
pg_dump -U agentapi agent_marketplace | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz
# Keep only last 7 days
find $BACKUP_DIR -mtime +7 -delete
```

```bash
chmod +x /home/agentapi/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /home/agentapi/backup.sh
```

---

## Summary

You now have Agent Marketplace API running on a Linux VM with:

- FastAPI application via systemd
- Celery worker for background tasks
- PostgreSQL database
- Redis cache
- MinIO object storage
- Nginx reverse proxy
- SSL via Let's Encrypt
- Firewall configured
- Logging enabled

For production, consider:
- Setting up monitoring (Prometheus + Grafana)
- Configuring log aggregation
- Setting up database replication
- Using a managed database service

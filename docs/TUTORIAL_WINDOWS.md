# Tutorial: Deploying on Windows

Step-by-step guide to deploy Agent Marketplace API on Windows 10/11 or Windows Server.

## Deployment Options

| Option | Best For | Complexity |
|--------|----------|------------|
| [WSL2 + Docker](#option-1-wsl2--docker-recommended) | Development, small production | Easy |
| [Native Windows](#option-2-native-windows) | When WSL2 not available | Medium |
| [Windows Server + IIS](#option-3-windows-server--iis) | Enterprise production | Advanced |

---

## Option 1: WSL2 + Docker (Recommended)

The easiest approach - run Linux containers on Windows using WSL2 and Docker Desktop.

### Step 1.1: Enable WSL2

Open PowerShell as Administrator:

```powershell
# Enable WSL
wsl --install

# Restart computer when prompted
Restart-Computer
```

After restart, open PowerShell again:

```powershell
# Set WSL2 as default
wsl --set-default-version 2

# Install Ubuntu
wsl --install -d Ubuntu-22.04

# Verify installation
wsl -l -v
```

### Step 1.2: Install Docker Desktop

1. Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. Run installer, ensure "Use WSL 2 instead of Hyper-V" is checked
3. Restart if prompted
4. Open Docker Desktop and complete setup

Verify in PowerShell:

```powershell
docker --version
docker compose version
```

### Step 1.3: Clone Repository

```powershell
# Create project directory
mkdir C:\Projects
cd C:\Projects

# Clone repository
git clone https://github.com/kmcallorum/agent-marketplace-ld-api.git
cd agent-marketplace-ld-api
```

### Step 1.4: Configure Environment

```powershell
# Copy example environment file
copy .env.example .env

# Edit with notepad or your preferred editor
notepad .env
```

Set your configuration:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/agent_marketplace

# Redis
REDIS_URL=redis://redis:6379/0

# S3/MinIO
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=changeme_minio_secret
S3_BUCKET=agents

# JWT - Generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=your_secure_jwt_secret_here

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

### Step 1.5: Start Services

```powershell
# Start all services
docker compose up -d

# Run database migrations
docker compose exec api uv run alembic upgrade head

# Verify everything is running
docker compose ps
```

### Step 1.6: Access the API

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001

### Step 1.7: Managing the Deployment

```powershell
# View logs
docker compose logs -f api

# Stop services
docker compose down

# Restart services
docker compose restart

# Update and rebuild
git pull
docker compose up -d --build
```

---

## Option 2: Native Windows

Run directly on Windows without WSL2 or Docker.

### Step 2.1: Install Python 3.11+

1. Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Run installer with these options checked:
   - "Add Python to PATH"
   - "Install for all users"
3. Verify installation:

```powershell
python --version
pip --version
```

### Step 2.2: Install uv Package Manager

```powershell
# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Restart PowerShell, then verify
uv --version
```

### Step 2.3: Install PostgreSQL

1. Download PostgreSQL 16 from [postgresql.org](https://www.postgresql.org/download/windows/)
2. Run installer:
   - Set password for postgres user
   - Keep default port 5432
   - Complete installation

3. Add to PATH (adjust version number if different):

```powershell
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"
[Environment]::SetEnvironmentVariable("Path", $env:Path, [EnvironmentVariableTarget]::User)
```

4. Create database:

```powershell
# Open psql
psql -U postgres

# In psql prompt:
CREATE USER agentapi WITH PASSWORD 'your_password';
CREATE DATABASE agent_marketplace OWNER agentapi;
GRANT ALL PRIVILEGES ON DATABASE agent_marketplace TO agentapi;
\q
```

### Step 2.4: Install Redis

Redis doesn't officially support Windows, but you can use:

**Option A: Memurai (Redis-compatible)**
1. Download from [memurai.com](https://www.memurai.com/get-memurai)
2. Install and start service

**Option B: Redis via WSL2**
```powershell
wsl --install -d Ubuntu-22.04
wsl -d Ubuntu-22.04 -e bash -c "sudo apt update && sudo apt install -y redis-server && sudo service redis-server start"
```

**Option C: Docker for Redis only**
```powershell
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Step 2.5: Install MinIO

1. Download MinIO server from [min.io](https://min.io/download#/windows)
2. Create directories:

```powershell
mkdir C:\minio\data
```

3. Create MinIO service (run PowerShell as Admin):

```powershell
# Download MinIO
Invoke-WebRequest -Uri "https://dl.min.io/server/minio/release/windows-amd64/minio.exe" -OutFile "C:\minio\minio.exe"

# Create startup script
@"
set MINIO_ROOT_USER=minioadmin
set MINIO_ROOT_PASSWORD=your_minio_password
C:\minio\minio.exe server C:\minio\data --console-address ":9001"
"@ | Out-File -FilePath "C:\minio\start-minio.bat" -Encoding ASCII

# Or run directly
$env:MINIO_ROOT_USER = "minioadmin"
$env:MINIO_ROOT_PASSWORD = "your_minio_password"
Start-Process -FilePath "C:\minio\minio.exe" -ArgumentList "server C:\minio\data --console-address :9001"
```

4. Create bucket using MinIO Client:

```powershell
# Download mc
Invoke-WebRequest -Uri "https://dl.min.io/client/mc/release/windows-amd64/mc.exe" -OutFile "C:\minio\mc.exe"

# Configure and create bucket
C:\minio\mc.exe alias set local http://localhost:9000 minioadmin your_minio_password
C:\minio\mc.exe mb local/agents
```

### Step 2.6: Clone and Setup Application

```powershell
cd C:\Projects
git clone https://github.com/kmcallorum/agent-marketplace-ld-api.git
cd agent-marketplace-ld-api

# Install dependencies
uv sync
```

### Step 2.7: Configure Environment

Create `.env` file:

```powershell
notepad .env
```

```bash
# Database
DATABASE_URL=postgresql+asyncpg://agentapi:your_password@localhost:5432/agent_marketplace

# Redis (adjust based on your Redis option)
REDIS_URL=redis://localhost:6379/0

# S3/MinIO
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=your_minio_password
S3_BUCKET=agents

# JWT
JWT_SECRET_KEY=your_secure_jwt_secret_at_least_32_characters

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/auth/github/callback

# API Settings
DEBUG=false
LOG_LEVEL=INFO
```

### Step 2.8: Run Migrations and Start

```powershell
# Run migrations
uv run alembic upgrade head

# Start API server
uv run uvicorn agent_marketplace_api.main:app --host 0.0.0.0 --port 8000
```

### Step 2.9: Run as Windows Service (Optional)

Use NSSM (Non-Sucking Service Manager) to run as a service:

1. Download NSSM from [nssm.cc](https://nssm.cc/download)
2. Extract to `C:\nssm`

```powershell
# Install API service
C:\nssm\nssm.exe install AgentMarketplaceAPI "C:\Users\<user>\.local\bin\uv.exe" "run uvicorn agent_marketplace_api.main:app --host 0.0.0.0 --port 8000"
C:\nssm\nssm.exe set AgentMarketplaceAPI AppDirectory "C:\Projects\agent-marketplace-ld-api"
C:\nssm\nssm.exe set AgentMarketplaceAPI AppEnvironmentExtra "PATH=C:\Users\<user>\.local\bin;%PATH%"

# Start service
C:\nssm\nssm.exe start AgentMarketplaceAPI

# Install Celery worker service
C:\nssm\nssm.exe install AgentMarketplaceWorker "C:\Users\<user>\.local\bin\uv.exe" "run celery -A agent_marketplace_api.tasks.celery worker --loglevel=info"
C:\nssm\nssm.exe set AgentMarketplaceWorker AppDirectory "C:\Projects\agent-marketplace-ld-api"
C:\nssm\nssm.exe start AgentMarketplaceWorker
```

---

## Option 3: Windows Server + IIS

For enterprise Windows Server deployments with IIS as reverse proxy.

### Step 3.1: Install Prerequisites

Open PowerShell as Administrator:

```powershell
# Install IIS with required features
Install-WindowsFeature -Name Web-Server, Web-WebSockets, Web-Http-Redirect -IncludeManagementTools

# Install URL Rewrite Module
# Download from: https://www.iis.net/downloads/microsoft/url-rewrite
# Or use chocolatey:
choco install urlrewrite -y

# Install Application Request Routing (ARR)
# Download from: https://www.iis.net/downloads/microsoft/application-request-routing
```

### Step 3.2: Install Python and Application

Follow Steps 2.1-2.8 from Option 2 above to install Python, dependencies, and configure the application.

### Step 3.3: Configure IIS as Reverse Proxy

1. Open IIS Manager
2. Create new website or use Default Web Site
3. Create `web.config` in the site root:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <rule name="ReverseProxyToAPI" stopProcessing="true">
                    <match url="(.*)" />
                    <conditions>
                        <add input="{CACHE_URL}" pattern="^(https?)://" />
                    </conditions>
                    <action type="Rewrite" url="{C:1}://localhost:8000/{R:1}" />
                </rule>
            </rules>
            <outboundRules>
                <rule name="RestoreAcceptEncoding" preCondition="NeedsRestoringAcceptEncoding">
                    <match serverVariable="HTTP_ACCEPT_ENCODING" pattern="^(.*)" />
                    <action type="Rewrite" value="{HTTP_X_ORIGINAL_ACCEPT_ENCODING}" />
                </rule>
                <preConditions>
                    <preCondition name="NeedsRestoringAcceptEncoding">
                        <add input="{HTTP_X_ORIGINAL_ACCEPT_ENCODING}" pattern=".+" />
                    </preCondition>
                </preConditions>
            </outboundRules>
        </rewrite>
        <httpProtocol>
            <customHeaders>
                <add name="X-Frame-Options" value="SAMEORIGIN" />
                <add name="X-Content-Type-Options" value="nosniff" />
                <add name="X-XSS-Protection" value="1; mode=block" />
            </customHeaders>
        </httpProtocol>
    </system.webServer>
</configuration>
```

### Step 3.4: Enable ARR Proxy

In IIS Manager:
1. Select server node
2. Open "Application Request Routing Cache"
3. Click "Server Proxy Settings"
4. Check "Enable proxy"
5. Apply changes

### Step 3.5: Configure SSL Certificate

```powershell
# Generate self-signed cert for testing
New-SelfSignedCertificate -DnsName "api.yourdomain.com" -CertStoreLocation "cert:\LocalMachine\My"

# For production, use Let's Encrypt with win-acme:
# Download from: https://www.win-acme.com/
```

### Step 3.6: Create Windows Services

Create PowerShell script `C:\Projects\agent-marketplace-ld-api\scripts\install-services.ps1`:

```powershell
# Download NSSM if not present
if (-not (Test-Path "C:\nssm\nssm.exe")) {
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "C:\nssm.zip"
    Expand-Archive -Path "C:\nssm.zip" -DestinationPath "C:\"
    Rename-Item "C:\nssm-2.24" "C:\nssm"
}

$uvPath = "$env:USERPROFILE\.local\bin\uv.exe"
$appDir = "C:\Projects\agent-marketplace-ld-api"

# API Service
& C:\nssm\nssm.exe install AgentMarketplaceAPI $uvPath
& C:\nssm\nssm.exe set AgentMarketplaceAPI AppParameters "run uvicorn agent_marketplace_api.main:app --host 127.0.0.1 --port 8000 --workers 4"
& C:\nssm\nssm.exe set AgentMarketplaceAPI AppDirectory $appDir
& C:\nssm\nssm.exe set AgentMarketplaceAPI DisplayName "Agent Marketplace API"
& C:\nssm\nssm.exe set AgentMarketplaceAPI Description "FastAPI backend for Agent Marketplace"
& C:\nssm\nssm.exe set AgentMarketplaceAPI Start SERVICE_AUTO_START
& C:\nssm\nssm.exe set AgentMarketplaceAPI AppStdout "$appDir\logs\api.log"
& C:\nssm\nssm.exe set AgentMarketplaceAPI AppStderr "$appDir\logs\api-error.log"
& C:\nssm\nssm.exe set AgentMarketplaceAPI AppRotateFiles 1
& C:\nssm\nssm.exe set AgentMarketplaceAPI AppRotateBytes 10485760

# Worker Service
& C:\nssm\nssm.exe install AgentMarketplaceWorker $uvPath
& C:\nssm\nssm.exe set AgentMarketplaceWorker AppParameters "run celery -A agent_marketplace_api.tasks.celery worker --loglevel=info"
& C:\nssm\nssm.exe set AgentMarketplaceWorker AppDirectory $appDir
& C:\nssm\nssm.exe set AgentMarketplaceWorker DisplayName "Agent Marketplace Worker"
& C:\nssm\nssm.exe set AgentMarketplaceWorker Description "Celery worker for Agent Marketplace"
& C:\nssm\nssm.exe set AgentMarketplaceWorker Start SERVICE_AUTO_START
& C:\nssm\nssm.exe set AgentMarketplaceWorker AppStdout "$appDir\logs\worker.log"
& C:\nssm\nssm.exe set AgentMarketplaceWorker AppStderr "$appDir\logs\worker-error.log"

# Create logs directory
New-Item -ItemType Directory -Force -Path "$appDir\logs"

# Start services
Start-Service AgentMarketplaceAPI
Start-Service AgentMarketplaceWorker

Write-Host "Services installed and started successfully!"
```

Run the script:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\install-services.ps1
```

### Step 3.7: Configure Firewall

```powershell
# Allow HTTP
New-NetFirewallRule -DisplayName "HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow

# Allow HTTPS
New-NetFirewallRule -DisplayName "HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

---

## Troubleshooting

### Python/uv Not Found

```powershell
# Check PATH
$env:Path -split ';' | Where-Object { $_ -like '*python*' -or $_ -like '*uv*' }

# Add to PATH manually
$env:Path += ";$env:USERPROFILE\.local\bin"
[Environment]::SetEnvironmentVariable("Path", $env:Path, [EnvironmentVariableTarget]::User)
```

### PostgreSQL Connection Issues

```powershell
# Check if PostgreSQL is running
Get-Service postgresql*

# Start if stopped
Start-Service postgresql-x64-16

# Test connection
psql -U agentapi -d agent_marketplace -h localhost
```

### Redis Connection Issues

```powershell
# If using Docker Redis
docker ps | findstr redis
docker start redis

# If using Memurai
Get-Service Memurai
Start-Service Memurai

# Test connection
redis-cli ping
```

### Port Already in Use

```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process by PID
taskkill /PID <pid> /F

# Or use different port
uv run uvicorn agent_marketplace_api.main:app --port 8001
```

### Service Won't Start

```powershell
# Check service status
Get-Service AgentMarketplaceAPI

# View Windows Event Log
Get-EventLog -LogName Application -Source nssm -Newest 10

# Check NSSM logs
C:\nssm\nssm.exe status AgentMarketplaceAPI

# View application logs
Get-Content C:\Projects\agent-marketplace-ld-api\logs\api-error.log -Tail 50
```

### WSL2 Issues

```powershell
# Check WSL status
wsl --status

# Restart WSL
wsl --shutdown
wsl

# Update WSL
wsl --update

# Reset distribution if needed
wsl --unregister Ubuntu-22.04
wsl --install -d Ubuntu-22.04
```

### Docker Desktop Issues

```powershell
# Restart Docker Desktop
Stop-Process -Name "Docker Desktop" -Force
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Reset Docker to factory defaults (WARNING: deletes all containers/images)
# Use Docker Desktop UI: Settings > Reset

# Check Docker daemon
docker info
```

---

## Performance Tips

### 1. Use SSD Storage

Store PostgreSQL data and MinIO data on SSD for better performance.

### 2. Increase Worker Count

```powershell
# For production, increase uvicorn workers
uv run uvicorn agent_marketplace_api.main:app --workers 4
```

### 3. Configure Windows for Performance

```powershell
# Disable Windows Defender real-time scanning for project folder (dev only)
Add-MpPreference -ExclusionPath "C:\Projects\agent-marketplace-ld-api"

# Increase file handle limits
# Edit registry: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters
# Add DWORD: MaxUserPort = 65534
```

### 4. Use WSL2 for Better I/O

WSL2 + Docker provides better file I/O performance than native Windows for this workload.

---

## Summary

**WSL2 + Docker (Recommended)**
- Easiest setup
- Best compatibility
- Same as Linux deployment
- Great for development and small production

**Native Windows**
- No virtualization required
- More complex setup
- Requires Windows-specific workarounds for Redis
- Good for environments where WSL2/Docker unavailable

**Windows Server + IIS**
- Enterprise-grade
- Integrates with Windows infrastructure
- SSL via Windows certificate store
- AD authentication possible
- Most complex setup

For most users, **WSL2 + Docker** is the recommended approach as it provides the best compatibility and easiest maintenance path.

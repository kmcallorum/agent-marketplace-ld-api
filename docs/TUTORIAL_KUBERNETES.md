# Tutorial: Deploying on Kubernetes / K3s

Step-by-step guide to deploy Agent Marketplace API on Kubernetes or K3s (lightweight Kubernetes).

## Prerequisites

- Linux server (Ubuntu 22.04 recommended) or existing K8s cluster
- Minimum 2 vCPU, 4GB RAM (for K3s single node)
- kubectl CLI installed
- Helm 3 installed (optional, for easier deployments)

## Part 1: K3s Installation (Skip if using existing cluster)

### Step 1.1: Install K3s

K3s is a lightweight Kubernetes distribution perfect for edge, IoT, and development.

```bash
# Install K3s (includes kubectl)
curl -sfL https://get.k3s.io | sh -

# Wait for K3s to be ready
sudo k3s kubectl get nodes

# Configure kubectl for your user
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config

# Verify
kubectl get nodes
kubectl get pods -A
```

### Step 1.2: Install Helm (Optional)

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

---

## Part 2: Prepare Kubernetes Resources

### Step 2.1: Create Namespace

```bash
kubectl create namespace agent-marketplace
kubectl config set-context --current --namespace=agent-marketplace
```

### Step 2.2: Create Directory Structure

```bash
mkdir -p k8s/{base,overlays/production}
cd k8s
```

---

## Part 3: Create Kubernetes Manifests

### Step 3.1: Secrets

Create `k8s/base/secrets.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: agent-marketplace-secrets
  namespace: agent-marketplace
type: Opaque
stringData:
  # Database
  DATABASE_URL: "postgresql+asyncpg://agentapi:your_db_password@postgres:5432/agent_marketplace"
  POSTGRES_PASSWORD: "your_db_password"

  # Redis
  REDIS_URL: "redis://redis:6379/0"

  # S3/MinIO
  S3_ENDPOINT: "http://minio:9000"
  S3_ACCESS_KEY: "minioadmin"
  S3_SECRET_KEY: "your_minio_password"
  S3_BUCKET: "agents"

  # JWT
  JWT_SECRET_KEY: "your_jwt_secret_at_least_32_characters_long"

  # GitHub OAuth
  GITHUB_CLIENT_ID: "your_github_client_id"
  GITHUB_CLIENT_SECRET: "your_github_client_secret"
```

Apply secrets:

```bash
kubectl apply -f k8s/base/secrets.yaml
```

### Step 3.2: ConfigMap

Create `k8s/base/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-marketplace-config
  namespace: agent-marketplace
data:
  JWT_ALGORITHM: "HS256"
  JWT_ACCESS_TOKEN_EXPIRE_MINUTES: "30"
  JWT_REFRESH_TOKEN_EXPIRE_DAYS: "7"
  DEBUG: "false"
  LOG_LEVEL: "INFO"
```

### Step 3.3: PostgreSQL

Create `k8s/base/postgres.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: agent-marketplace
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: local-path  # K3s default storage class
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: agent-marketplace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_USER
              value: "agentapi"
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: agent-marketplace-secrets
                  key: POSTGRES_PASSWORD
            - name: POSTGRES_DB
              value: "agent_marketplace"
          volumeMounts:
            - name: postgres-data
              mountPath: /var/lib/postgresql/data
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "agentapi"]
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            exec:
              command: ["pg_isready", "-U", "agentapi"]
            initialDelaySeconds: 30
            periodSeconds: 10
      volumes:
        - name: postgres-data
          persistentVolumeClaim:
            claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: agent-marketplace
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
```

### Step 3.4: Redis

Create `k8s/base/redis.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: agent-marketplace
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: local-path
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: agent-marketplace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          command: ["redis-server", "--appendonly", "yes"]
          ports:
            - containerPort: 6379
          volumeMounts:
            - name: redis-data
              mountPath: /data
          resources:
            requests:
              memory: "64Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "250m"
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 30
            periodSeconds: 10
      volumes:
        - name: redis-data
          persistentVolumeClaim:
            claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: agent-marketplace
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
```

### Step 3.5: MinIO

Create `k8s/base/minio.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: minio-pvc
  namespace: agent-marketplace
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: local-path
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
  namespace: agent-marketplace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
        - name: minio
          image: minio/minio:latest
          command: ["server", "/data", "--console-address", ":9001"]
          ports:
            - containerPort: 9000
              name: api
            - containerPort: 9001
              name: console
          env:
            - name: MINIO_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: agent-marketplace-secrets
                  key: S3_ACCESS_KEY
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: agent-marketplace-secrets
                  key: S3_SECRET_KEY
          volumeMounts:
            - name: minio-data
              mountPath: /data
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          readinessProbe:
            httpGet:
              path: /minio/health/ready
              port: 9000
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /minio/health/live
              port: 9000
            initialDelaySeconds: 30
            periodSeconds: 10
      volumes:
        - name: minio-data
          persistentVolumeClaim:
            claimName: minio-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: agent-marketplace
spec:
  selector:
    app: minio
  ports:
    - port: 9000
      targetPort: 9000
      name: api
    - port: 9001
      targetPort: 9001
      name: console
---
# Job to create bucket on startup
apiVersion: batch/v1
kind: Job
metadata:
  name: minio-setup
  namespace: agent-marketplace
spec:
  template:
    spec:
      containers:
        - name: mc
          image: minio/mc:latest
          command:
            - /bin/sh
            - -c
            - |
              sleep 15
              mc alias set local http://minio:9000 $S3_ACCESS_KEY $S3_SECRET_KEY
              mc mb local/$S3_BUCKET --ignore-existing
          env:
            - name: S3_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: agent-marketplace-secrets
                  key: S3_ACCESS_KEY
            - name: S3_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: agent-marketplace-secrets
                  key: S3_SECRET_KEY
            - name: S3_BUCKET
              valueFrom:
                secretKeyRef:
                  name: agent-marketplace-secrets
                  key: S3_BUCKET
      restartPolicy: OnFailure
  backoffLimit: 3
```

### Step 3.6: API Deployment

Create `k8s/base/api.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-marketplace-api
  namespace: agent-marketplace
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agent-marketplace-api
  template:
    metadata:
      labels:
        app: agent-marketplace-api
    spec:
      initContainers:
        # Wait for postgres to be ready
        - name: wait-for-postgres
          image: postgres:16-alpine
          command:
            - /bin/sh
            - -c
            - |
              until pg_isready -h postgres -U agentapi; do
                echo "Waiting for postgres..."
                sleep 2
              done
        # Run migrations
        - name: migrations
          image: ghcr.io/kmcallorum/agent-marketplace-ld-api:latest
          command: ["uv", "run", "alembic", "upgrade", "head"]
          envFrom:
            - secretRef:
                name: agent-marketplace-secrets
            - configMapRef:
                name: agent-marketplace-config
      containers:
        - name: api
          image: ghcr.io/kmcallorum/agent-marketplace-ld-api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: agent-marketplace-secrets
            - configMapRef:
                name: agent-marketplace-config
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
            timeoutSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: agent-marketplace-api
  namespace: agent-marketplace
spec:
  selector:
    app: agent-marketplace-api
  ports:
    - port: 80
      targetPort: 8000
```

### Step 3.7: Celery Worker Deployment

Create `k8s/base/worker.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-marketplace-worker
  namespace: agent-marketplace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: agent-marketplace-worker
  template:
    metadata:
      labels:
        app: agent-marketplace-worker
    spec:
      initContainers:
        - name: wait-for-redis
          image: redis:7-alpine
          command:
            - /bin/sh
            - -c
            - |
              until redis-cli -h redis ping; do
                echo "Waiting for redis..."
                sleep 2
              done
      containers:
        - name: worker
          image: ghcr.io/kmcallorum/agent-marketplace-ld-api:latest
          command: ["uv", "run", "celery", "-A", "agent_marketplace_api.tasks.celery", "worker", "--loglevel=info"]
          envFrom:
            - secretRef:
                name: agent-marketplace-secrets
            - configMapRef:
                name: agent-marketplace-config
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "2000m"
```

### Step 3.8: Ingress

Create `k8s/base/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-marketplace-ingress
  namespace: agent-marketplace
  annotations:
    # For K3s Traefik
    kubernetes.io/ingress.class: traefik
    # For cert-manager (if installed)
    # cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  rules:
    - host: api.your-domain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: agent-marketplace-api
                port:
                  number: 80
  # Uncomment for TLS
  # tls:
  #   - hosts:
  #       - api.your-domain.com
  #     secretName: agent-marketplace-tls
```

### Step 3.9: Kustomization

Create `k8s/base/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: agent-marketplace

resources:
  - secrets.yaml
  - configmap.yaml
  - postgres.yaml
  - redis.yaml
  - minio.yaml
  - api.yaml
  - worker.yaml
  - ingress.yaml
```

---

## Part 4: Deploy to Cluster

### Step 4.1: Apply All Resources

```bash
# Apply using kustomize
kubectl apply -k k8s/base/

# Or apply individually
kubectl apply -f k8s/base/secrets.yaml
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/postgres.yaml
kubectl apply -f k8s/base/redis.yaml
kubectl apply -f k8s/base/minio.yaml
kubectl apply -f k8s/base/api.yaml
kubectl apply -f k8s/base/worker.yaml
kubectl apply -f k8s/base/ingress.yaml
```

### Step 4.2: Verify Deployment

```bash
# Check all pods
kubectl get pods -n agent-marketplace

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n agent-marketplace --timeout=300s

# Check services
kubectl get svc -n agent-marketplace

# Check ingress
kubectl get ingress -n agent-marketplace

# View logs
kubectl logs -f deployment/agent-marketplace-api -n agent-marketplace
```

### Step 4.3: Test Deployment

```bash
# Port forward to test locally
kubectl port-forward svc/agent-marketplace-api 8000:80 -n agent-marketplace

# In another terminal
curl http://localhost:8000/health
```

---

## Part 5: TLS/SSL with cert-manager

### Step 5.1: Install cert-manager

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# Wait for cert-manager to be ready
kubectl wait --for=condition=ready pod -l app=cert-manager -n cert-manager --timeout=120s
```

### Step 5.2: Create ClusterIssuer

Create `k8s/base/cluster-issuer.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: traefik
```

```bash
kubectl apply -f k8s/base/cluster-issuer.yaml
```

### Step 5.3: Update Ingress for TLS

Update `k8s/base/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-marketplace-ingress
  namespace: agent-marketplace
  annotations:
    kubernetes.io/ingress.class: traefik
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  rules:
    - host: api.your-domain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: agent-marketplace-api
                port:
                  number: 80
  tls:
    - hosts:
        - api.your-domain.com
      secretName: agent-marketplace-tls
```

```bash
kubectl apply -f k8s/base/ingress.yaml
```

---

## Part 6: Scaling and High Availability

### Step 6.1: Horizontal Pod Autoscaler

Create `k8s/base/hpa.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-marketplace-api-hpa
  namespace: agent-marketplace
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agent-marketplace-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-marketplace-worker-hpa
  namespace: agent-marketplace
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agent-marketplace-worker
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

```bash
kubectl apply -f k8s/base/hpa.yaml
```

### Step 6.2: Pod Disruption Budget

Create `k8s/base/pdb.yaml`:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: agent-marketplace-api-pdb
  namespace: agent-marketplace
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: agent-marketplace-api
```

---

## Part 7: Monitoring

### Step 7.1: Install Prometheus Stack with Helm

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.adminPassword=admin
```

### Step 7.2: Create ServiceMonitor

Create `k8s/base/servicemonitor.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: agent-marketplace-api
  namespace: agent-marketplace
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: agent-marketplace-api
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### Step 7.3: Access Grafana

```bash
kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring
# Open http://localhost:3000 (admin/admin)
```

---

## Part 8: Backup and Disaster Recovery

### Step 8.1: Database Backup CronJob

Create `k8s/base/backup-cronjob.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: agent-marketplace
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:16-alpine
              command:
                - /bin/sh
                - -c
                - |
                  BACKUP_FILE="/backup/db_$(date +%Y%m%d_%H%M%S).sql.gz"
                  pg_dump -h postgres -U agentapi agent_marketplace | gzip > $BACKUP_FILE
                  echo "Backup created: $BACKUP_FILE"
                  # Keep only last 7 days
                  find /backup -mtime +7 -delete
              env:
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: agent-marketplace-secrets
                      key: POSTGRES_PASSWORD
              volumeMounts:
                - name: backup-volume
                  mountPath: /backup
          volumes:
            - name: backup-volume
              persistentVolumeClaim:
                claimName: backup-pvc
          restartPolicy: OnFailure
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: backup-pvc
  namespace: agent-marketplace
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: local-path
```

---

## Part 9: Updates and Rollbacks

### Step 9.1: Rolling Update

```bash
# Update image
kubectl set image deployment/agent-marketplace-api \
  api=ghcr.io/kmcallorum/agent-marketplace-ld-api:v1.2.0 \
  -n agent-marketplace

# Watch rollout
kubectl rollout status deployment/agent-marketplace-api -n agent-marketplace
```

### Step 9.2: Rollback

```bash
# View rollout history
kubectl rollout history deployment/agent-marketplace-api -n agent-marketplace

# Rollback to previous version
kubectl rollout undo deployment/agent-marketplace-api -n agent-marketplace

# Rollback to specific revision
kubectl rollout undo deployment/agent-marketplace-api --to-revision=2 -n agent-marketplace
```

---

## Part 10: Useful Commands

```bash
# View all resources
kubectl get all -n agent-marketplace

# View pods with more details
kubectl get pods -n agent-marketplace -o wide

# Describe pod (for troubleshooting)
kubectl describe pod <pod-name> -n agent-marketplace

# View logs
kubectl logs -f deployment/agent-marketplace-api -n agent-marketplace

# View logs from all pods
kubectl logs -f -l app=agent-marketplace-api -n agent-marketplace

# Execute command in pod
kubectl exec -it deployment/agent-marketplace-api -n agent-marketplace -- bash

# Port forward
kubectl port-forward svc/agent-marketplace-api 8000:80 -n agent-marketplace

# Scale manually
kubectl scale deployment agent-marketplace-api --replicas=3 -n agent-marketplace

# View resource usage
kubectl top pods -n agent-marketplace

# Delete and recreate
kubectl delete -k k8s/base/ && kubectl apply -k k8s/base/
```

---

## Troubleshooting

### Pods Stuck in Pending

```bash
# Check events
kubectl get events -n agent-marketplace --sort-by='.lastTimestamp'

# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"
```

### Pod CrashLoopBackOff

```bash
# Check logs
kubectl logs <pod-name> -n agent-marketplace --previous

# Check pod events
kubectl describe pod <pod-name> -n agent-marketplace
```

### Database Connection Issues

```bash
# Check postgres is running
kubectl get pods -l app=postgres -n agent-marketplace

# Check postgres logs
kubectl logs -l app=postgres -n agent-marketplace

# Test connection from API pod
kubectl exec -it deployment/agent-marketplace-api -n agent-marketplace -- \
  python -c "import asyncio; from sqlalchemy.ext.asyncio import create_async_engine; print('OK')"
```

### Ingress Not Working

```bash
# Check ingress controller
kubectl get pods -n kube-system | grep traefik

# Check ingress
kubectl describe ingress agent-marketplace-ingress -n agent-marketplace

# Check if service is reachable
kubectl port-forward svc/agent-marketplace-api 8000:80 -n agent-marketplace
```

---

## Summary

You now have Agent Marketplace API running on Kubernetes/K3s with:

- PostgreSQL with persistent storage
- Redis with persistent storage
- MinIO object storage
- API deployment with health checks
- Celery worker for background tasks
- Ingress with optional TLS
- Horizontal Pod Autoscaling
- Monitoring with Prometheus/Grafana
- Automated backups

For production, consider:
- Using managed database services (RDS, Cloud SQL)
- Multi-node cluster for high availability
- External secrets management (Vault, External Secrets)
- GitOps with ArgoCD or Flux
- Network policies for security

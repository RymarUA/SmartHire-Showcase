# Infrastructure & Deployment

SmartHire supports multiple deployment options: Docker Compose for development, and Kubernetes Helm for production.

## Docker Compose (Development)

```bash
# Core services (postgres + redis)
docker compose --profile core up -d

# With bot
docker compose --profile bot up -d

# With API
docker compose --profile api up -d

# Full stack
docker compose --profile all up -d
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| postgres | 5500 | PostgreSQL 16 |
| redis | 6379 | Redis 7 (cache, rate limit, FSM) |
| bot | 8443 | Telegram bot (aiogram) |
| api | 8000 | FastAPI REST API |

## Docker Compose with Monitoring

```bash
# Start monitoring stack
docker compose -f docker-compose.monitoring.yml up -d

# Access
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
# - Tempo (traces): http://localhost:3200
```

### Monitoring Stack

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:v2.53.0
    ports:
      - "9090:9090"
    volumes:
      - ./infrastructure/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro

  grafana:
    image: grafana/grafana-oss:11.1.0
    ports:
      - "3000:3000"

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.103.0
    ports:
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP

  tempo:
    image: grafana/tempo:2.5.0
    ports:
      - "3200:3200"
```

## Kubernetes (Production)

SmartHire uses Helm for Kubernetes deployment with auto-scaling and zero-downtime rollouts.

### Helm Chart Structure

```
helm/smart-os/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── hpa.yaml              # Horizontal Pod Autoscaler
│   ├── pdb.yaml              # PodDisruptionBudget
│   ├── ingress.yaml
│   └── configmap.yaml
└── templates/tests/
    └── test-connection.yaml
```

### Key Features

```yaml
# values.yaml
replicaCount: 3

autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 75
  targetMemoryUtilizationPercentage: 75

securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 512Mi

livenessProbe:
  httpGet:
    path: /health
    port: 8443
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /readiness
    port: 8443
  initialDelaySeconds: 10
  periodSeconds: 5
```

### Deployment Commands

```bash
# Install
helm install smarthire helm/smart-os/ \
  --namespace smarthire \
  --create-namespace \
  --values helm/smart-os/values.yaml

# Upgrade
helm upgrade smarthire helm/smart-os/ \
  --namespace smarthire \
  --values helm/smart-os/values.yaml

# Uninstall
helm uninstall smarthire --namespace smarthire
```

### Pre-install Hook (Migrations)

The Helm chart includes a pre-install hook that runs database migrations before deployment:

```yaml
# templates/job-migrations.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ .Release.Name }}-migrations
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
spec:
  template:
    spec:
      containers:
        - name: migrations
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          command: ["python", "scripts/run_migrations.py"]
      restartPolicy: OnFailure
```

### PodDisruptionBudget

Ensures zero-downtime rollouts:

```yaml
# templates/pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ .Release.Name }}-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: {{ .Release.Name }}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection | required |
| REDIS_HOST | Redis host | localhost |
| REDIS_PORT | Redis port | 6379 |
| BOT_TOKEN | Telegram bot token | required |
| ENCRYPTION_KEY | AES-256 key for PII | required |
| PAYMENT_PROVIDER | wayforpay or liqpay | - |

## Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness probe |
| `GET /readiness` | Readiness (DB, Redis, Telegram) |
| `GET /metrics` | Prometheus scrape endpoint |

## References

- Docker Compose: `docker-compose.yml`
- Monitoring: `docker-compose.monitoring.yml`
- Helm Chart: `helm/smart-os/`

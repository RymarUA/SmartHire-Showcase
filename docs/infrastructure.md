# Infrastructure & Deployment

SmartHire deployment today is **Docker Compose with blue-green deploys**.
Kubernetes/Helm is a designed target — deliberately deferred by ADR until
the scale trigger (~100 active tenants) makes the ops tax worth it.

## Production Path: Blue-Green Compose

Two color instances (bot/api) run behind the edge proxy; `deploy.sh`
handles the flip:

1. Detect the live color (queries both instances — ambiguous state refuses
   rather than guesses).
2. Bring up the other color with the new image.
3. **In-container readiness probes** (`bot /ready`, `api /readiness`) —
   the health gate measures the fleet being deployed, not a proxy 200.
4. DB backup, atomic switch, scoped rollback on failure.

Compose files per environment: `docker-compose.yml` (base + profiles),
`.dev`, `.ci`, `.staging`, `.prod`, `.monitoring`, `.multi-instance`
(3 replicas + Sentinel + Nginx LB — validated on a bench stack).

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
| redis | 6379 | Redis 7 (cache, rate limit, FSM, distributed locks) |
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

### Monitoring Stack (sketch)

```yaml
# docker-compose.monitoring.yml (excerpt)
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

## Kubernetes (designed target — deferred)

The platform is designed K8s-native (stateless app pods, externalized state,
readiness probes, expand-contract migrations) but the Helm chart is **not
deployed today** — it activates when tenant count justifies the ops cost.
The values below are the *design target*, not a production export.

### Designed Chart Structure

```
helm/smart-os/            # design target — not shipped
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

### Target Values (excerpt)

```yaml
# code/helm_values.yaml — design target values
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

### Designed Pre-install Hook (Migrations)

```yaml
# Design target: run migrations before new pods start
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

### Designed PodDisruptionBudget

```yaml
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

- Docker Compose: `docker-compose.yml` (+ `.dev/.ci/.staging/.prod/.monitoring/.multi-instance`)
- Monitoring: `docker-compose.monitoring.yml`
- K8s design values: `code/helm_values.yaml`

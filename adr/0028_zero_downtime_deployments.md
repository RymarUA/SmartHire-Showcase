# ADR-0028: Zero-Downtime Deployments via Helm + Expand-Contract

**Status:** Accepted  
**Date:** 2025-04-22  
**Last reviewed:** 2026-04-19

## Context

With tenants depending on the bot 24/7, any deployment downtime means lost revenue and support
tickets. PostgreSQL schema migrations are the highest-risk part of deploys: a `NOT NULL` column
addition without a default instantly breaks old pods still running during a rolling update.

## Decision

### Kubernetes Helm Chart Design

```yaml
# helm/smart-os/values.yaml (excerpt)
replicaCount: 2
autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 75

podDisruptionBudget:
  minAvailable: 1       # always keep at least 1 pod running

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

Pre-install hook runs `alembic upgrade head` **before** new pods start. Old pods stay up
and serve traffic during migration.

### Expand-Contract Migration Discipline

Every schema change follows a 3-release cycle:

```
Release N:    expand   — ADD COLUMN new_col NULLABLE, app writes both columns
              backfill — UPDATE SET new_col = old_col WHERE new_col IS NULL (batched)
Release N+1:  contract — app reads new_col only, stops writing old_col
Release N+2:  drop     — DROP COLUMN old_col (safe: no app references it)
```

This guarantees old and new app versions can run simultaneously during rolling update.

### Readiness Probe (4 dependencies)

```python
@router.get("/health/ready")
async def readiness() -> dict[str, str]:
    checks = await asyncio.gather(
        check_postgres(), check_redis(), check_telegram_api(), check_payment_provider(),
        return_exceptions=True,
    )
    if any(isinstance(c, Exception) for c in checks):
        raise HTTPException(status_code=503, detail="dependency unavailable")
    return {"status": "ready"}
```

A pod is not added to the load balancer until all 4 dependencies respond.

## Consequences

### Positive
- Zero downtime deploys measured over 40+ production releases.
- Rolling update takes ~3 minutes (HPA + PDB ensure continuity).
- Expand-contract prevents "migration of death" that kills running pods.
- Security context: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `drop: [ALL]`.

### Negative
- 3-release cycle slows down breaking schema changes.
- Pre-install Alembic hook means migration errors block the entire deploy.
- Backfill of large tables (>10M rows) requires batched execution to avoid lock contention.

## References

- `code/helm_values.yaml` — sanitized Helm values excerpt.
- ADR-0019: Payment Idempotency (migration discipline applies to payment tables too).
- ADR-0014: Money as Basis Points (BIGINT migration used expand-contract).

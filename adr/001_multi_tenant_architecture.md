# ADR-001: Multi-Tenant Architecture

**Status:** Accepted
**Last reviewed:** 2026-04-19
**Next review:** 2026-10-19

## Context

SmartHire is a B2B SaaS product that needs to serve multiple clients (tenants) while ensuring:
1. Data isolation between clients.
2. No accidental data leaks in webhooks and APIs.
3. Scalability and simple deployment of new tenants.

## Decision

We chose "logical isolation" model (Shared Database / Shared Schema). All key entities either have `tenant_id` context passed through, or the DB connection pool is instantiated for a specific tenant.

For cache (Redis), isolation is done through prefixes (key scoping: `tenant:{tenant_id}:*`).

## Consequences

### Positive
- Simple codebase and deployment management (one application serves all).
- Cache isolation prevents conflicts in rate limiting and session state.
- Simple API routing via `X-Tenant-ID`.

### Negative
- Developers must always remember to pass `tenant_id` in SQL queries or Gateway constructors.
- Complicates migrations of existing (single-user) tables and webhooks.

## Implementation

Implementation is based on:
- `core/tenant_context.py` (storing `tenant_id` in `contextvars`).
- `core/white_label/tenant_config.py` (tenant configurations).
- `core/repositories/tenant_decorator.py` - `@tenant_scoped` decorator for automatic tenant_id extraction.

## Tenant Isolation Patterns

### 1. Database Level (Row-Level Security)

```python
# All queries automatically include tenant_id
from core.repositories.sqlalchemy_helpers import TenantQueryBuilder

builder = TenantQueryBuilder(tenant_id="tenant_123")
stmt = builder.select(Anketa).where(Anketa.status == "opened")
# SELECT * FROM ankety WHERE status = $1 AND tenant_id = $2
```

### 2. Cache Level (Key Scoping)

```python
# Redis keys are prefixed with tenant_id
await redis.set(f"tenant:{tenant_id}:config", json.dumps(config))
await redis.get(f"tenant:{tenant_id}:config")
```

### 3. API Level (Header)

```python
# X-Tenant-ID header for tenant identification
@app.middleware("http")
async def tenant_context_middleware(request, call_next):
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        with set_tenant_id(tenant_id):
            return await call_next(request)
    return JSONResponse(status_code=401, body={"error": "Missing tenant"})
```

## References

- TenantContext: `core/tenant_context.py`
- TenantQueryBuilder: `code/tenant_query_builder.py`
- TenantConfig: `core/white_label/tenant_config.py`

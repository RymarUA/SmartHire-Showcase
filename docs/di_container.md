# Typed Dependency Injection (Dishka)

SmartHire uses **Dishka** for typed dependency injection (`core/di_v2/`). All
services resolve through typed scopes with explicit lifetimes — no global state,
no `Any`-typed provider calls, no `# type: ignore` on service boundaries.

Legacy `dependency-injector` container was fully removed (ADR-0048).

## Lifetimes

| Lifetime | Scope | Examples |
|----------|-------|----------|
| Application | one per process | DB pool, Redis client, config |
| Request/tenant | per request or per update | Gateways, Services — always carry explicit `tenant_id` |
| Action | per business operation | Short-lived command handlers |
| System/platform | cross-tenant operations | Admin surfaces, platform analytics |

Tenant-scoped objects are **never** application singletons.

## Composition Root

One typed composition root serves all three transports:

```
┌──────────────────────────────────────────────────────┐
│              core/di_v2/  (typed scopes)             │
│                                                      │
│   user_service_scope(tenant_id)                      │
│   anketa_service_scope(tenant_id)                    │
│   payment_service_scope(tenant_id)                   │
│   ticket_service_scope(tenant_id)                    │
│   billing_service_scope(tenant_id)                   │
│   ... ~60 typed resolver functions                   │
└──────────┬───────────────┬───────────────┬───────────┘
           │               │               │
     FastAPI request   Aiogram update   APScheduler job
     (per-request      (per-update      (explicit task
      scope)            middleware)      scope)
```

## Key Pattern

```python
# Scope entry point: typed chain, fail-closed
async with user_service_scope(tenant_id) as user_service:
    await user_service.notify_subscribers(anketa_id)

# Missing tenant_id or unavailable DB pool -> raises.
# It never silently proceeds without tenant context.
```

Background jobs open the same typed scope explicitly — no global container access:

```python
async def refresh_messages(tenant_id: str) -> None:
    async with user_service_scope(tenant_id) as user_service:
        ...
```

## Fail-Closed Rule

Every tenant-scoped scope **fails closed**: when `tenant_id` is missing or the
database pool is unavailable, resolution raises instead of proceeding without
tenant context. A background job that cannot establish tenant scope marks its
work failed (dead-letter) rather than running unscoped.

## Anti-Pattern: Removed with the Legacy Container

```python
# LEGACY (deleted): service locator, Any-typed, implicit lifetimes
service = get_container().user_service()      # -> Any
gateway = get_gateway("user", tenant_id)      # cached by (name, tenant_id)

# TYPED (current): explicit scope, concrete types
async with user_service_scope(tenant_id) as service:
    ...
```

## Benefits

1. **Concrete types at boundaries** — no `cast()`, no `no-any-return` suppressions
2. **Explicit tenant/system scopes** — isolation is visible in signatures
3. **One composition root** — FastAPI, Aiogram, and scheduler share it
4. **Testable** — typed provider overrides instead of container patching

## References

- ADR-0048: Typed Dependency Injection Migration
- ADR-0052: Composition root extraction
- ADR-0032: Service layer enforcement
- Services: `core/services/`

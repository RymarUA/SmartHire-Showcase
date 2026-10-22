# ADR 0048: Typed Dependency Injection Migration

**Status:** Completed (migration finished 2026-08-13)
**Date:** 2026-08-05
**Author:** SmartHire Architecture Team
**Supersedes:** ADR 004 (legacy `dependency-injector` container — deleted)

## Context

The original DI layer used `dependency-injector` `DynamicContainer` with providers
assigned as runtime attributes. Every provider call returned `Any`, so public
accessors carried `# type: ignore[no-any-return]` and the type system could not see
service boundaries. A separate `get_gateway()` locator cached gateways by
`(name, tenant_id)` with lifetime semantics that differed from the container's.

The application has three dependency lifecycles that must coexist:

1. **FastAPI requests** — per-request scope
2. **Aiogram updates** — per-update scope
3. **Background jobs** (APScheduler, workers) — explicit task scope

Tenant context must be explicit in all three. A tenant-scoped object must never
become an application singleton.

## Decision

Migrate to **Dishka** typed DI using a strangler strategy:

1. Keep the legacy container unchanged during migration; introduce a separate
   typed entry point (`core/di_v2/`).
2. Migrate consumers by vertical slices — one service chain at a time.
3. Require the typed spike to pass all three transports (FastAPI lifespan,
   Aiogram middleware, scheduler-style resolution) before production migration.
4. Model lifetimes explicitly: application / request-tenant / action / system.
5. Remove the legacy container and `dependency-injector` only after every
   consumer and lifecycle path has migrated.

The migration is complete: `get_container()` and `get_gateway()` are removed from
production code, `dependency-injector` is no longer a dependency, and `core/di_v2/`
provides ~60 typed resolver functions with per-service scope entry points
(`user_service_scope`, `anketa_service_scope`, `payment_service_scope`, …).

Every scope **fails closed**: when `tenant_id` is missing or the DB pool is
unavailable, resolution raises instead of silently proceeding without tenant context.

## Consequences

- **Positive:** DI boundaries expose concrete types without `cast()` or
  `no-any-return` suppressions; tenant scope and system scope are explicit
  concepts; FastAPI, Aiogram, and scheduler share one typed composition root.
- **Negative:** two DI systems coexisted during the migration window; test
  overrides migrated from container patching to typed provider overrides;
  circular imports had to be resolved before constructor injection.
- **Neutral:** runtime tenant isolation remains a database/runtime invariant —
  typed DI complements RLS, it does not replace it (see ADR 001).

## Key Pattern

```python
# LEGACY (removed): service locator with Any-typed accessors
service = get_container().user_service()        # -> Any
gateway = get_gateway("user", tenant_id)        # cached, implicit lifetime

# TYPED (current): explicit scope, concrete types, fail-closed
async with user_service_scope(tenant_id) as user_service:
    await user_service.notify_subscribers(anketa_id)
```

Background jobs open the same typed scope explicitly — no global container access:

```python
# APScheduler job: tenant id flows through scheduler args
async def refresh_messages(tenant_id: str):
    async with user_service_scope(tenant_id) as user_service:
        ...
```

## References

- Superseded: ADR 004 (legacy DI container)
- Composition root extraction: ADR 0052
- Service layer enforcement: ADR 0032
- Multi-tenancy hardening: ADR 0030

# ADR 0030: Multitenancy Hardening

**Date:** 2026-04-24
**Status:** completed
**Author:** SmartHire Architecture Team

## Context

A production multi-tenant SaaS platform needs to support multiple tenants without code changes. Several blocking issues were identified that prevent seamless multi-tenant operation:

1. **B4**: NameError in fallback error handling
2. **B3**: Missing `tenant_id` parameterization in config initialization
3. **B1**: Global admin IDs causing cross-tenant notification leak
4. **B2**: Mini App tenant resolution using wrong fallback logic

## Decision

### B4: Fix NameError in Fallback

Replace undefined variable with proper error handling in tenant config.

### B3: Parameterize Config Initialization

`init_white_label_config(tenant_id: str = "default")` parameterized with tenant_id in WHERE clause. Called for all tenants via `get_active_tenant_ids()` at startup.

### B1: Per-Tenant Admin Notifications

`notify_all_admins(bot, text, *, tenant_id=None)` updated with tenant-scoped notifications. `SUPERADMIN_IDS` used for background tasks (not tenant-specific admin IDs). `get_tenant_admin_ids(tenant_id, session)` implemented for per-tenant admins.

### B2: Mini App Tenant Resolution

Removed 5-column fallback in tenant resolution, left only `tenant_staff` lookup (for dev mode). Middleware correctly sets `tenant_id` through `set_tenant_id()`.

## Consequences

### Positive

- Multiple tenants can be connected without code changes
- Each tenant has their own admins through TenantStaff table
- Background tasks notify platform superadmins, not tenant admins
- No cross-tenant config leakage
- Mini App works only through `bot_id` resolution (secure)

### Negative

- Requires TenantStaff table population for each tenant
- Background tasks must be wrapped in `tenant_context()`

## Implementation

| Component | Status |
|-----------|--------|
| `init_white_label_config(tenant_id)` | ✅ |
| Per-tenant admin notifications | ✅ |
| Mini App tenant resolution | ✅ |
| TenantContext wrapper | ✅ |

## References

- TenantStaff model: `db/models.py`
- TenantQueryBuilder: `core/repositories/sqlalchemy_helpers.py`

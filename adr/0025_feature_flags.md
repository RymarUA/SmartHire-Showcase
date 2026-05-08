# ADR-0025: Feature Flags as Per-Tenant Kill-Switch

**Status:** Accepted  
**Date:** 2025-03-01  
**Last reviewed:** 2026-04-19

## Context

With 1000+ tenants in a single runtime, deploying a risky feature to all tenants simultaneously
is unacceptable. We need the ability to:
- Roll out features to a subset of tenants.
- Disable a broken feature for one tenant in under 60 seconds — no release, no restart.
- Give tenant admins control over opt-in features via Dashboard.

## Decision

Feature flags stored in `feature_flags` table, keyed by `(tenant_id, flag_name)`.
In-process cache (Redis, TTL 30s) prevents DB round-trips on every request.

```python
# Usage in any handler or service
from core.features.flags import is_enabled

if await is_enabled("new_booking_flow", tenant_id=tenant_id):
    return await new_booking_handler(...)
return await legacy_booking_handler(...)
```

All new non-trivial features are gated by default (`enabled=False` globally,
opt-in per tenant via Dashboard or CLI).

CLI for ops without UI:
```bash
uv run python scripts/run.py dev flags enable NEW_BOOKING_FLOW --tenant acme
uv run python scripts/run.py dev flags disable NEW_BOOKING_FLOW --all
```

## Consequences

### Positive
- Broken feature isolated to one tenant in < 60s (Dashboard toggle → Redis TTL expires).
- Gradual rollout: enable for 5% of tenants, monitor metrics, expand.
- Per-tenant toggles give enterprise clients control without support tickets.
- `WHITE_LABEL_ENABLED`, `PAYMENT_PROVIDER_LIQPAY`, `NEW_BOOKING_FLOW` all use the same mechanism.

### Negative
- Flag proliferation without cleanup creates dead code paths.
- TTL 30s means a broken feature can affect a tenant for up to 30s after disabling.
- Developers must remember to remove flags after full rollout (tracked in backlog).

## Governance

Flags older than 90 days with `enabled=True` for all tenants are candidates for hardcoding.
Reviewed in monthly tech debt session.

## References

- ADR-0021: White Label Configuration (`WHITE_LABEL_ENABLED` uses this mechanism).
- ADR-001: Multi-Tenant Architecture (flags are strictly tenant-scoped).

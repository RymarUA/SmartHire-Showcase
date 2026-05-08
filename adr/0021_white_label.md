# ADR-0021: White Label Configuration Strategy

**Status:** Accepted  
**Date:** 2025-02-08  
**Last reviewed:** 2026-04-19

## Context

SmartHire tenants want to present the platform under their own brand: custom bot name, logo,
legal entity details, payment provider, pricing, and document links. We needed a config strategy
that allows onboarding a new brand in minutes while supporting runtime overrides without a release.

## Decision

Two-tier configuration with a feature-flag switch:

### Tier 1 — Static YAML (default, `WHITE_LABEL_ENABLED=false`)

Files in `core/white_label/clients/<client_id>.yaml`. Version-controlled, reviewed via PR.

```yaml
# core/white_label/clients/acme.yaml
brand_name: "HireBot Pro"
owner_name: "ФОП Іваненко О.П."
tariff_amount: 1200.0        # display only; stored as kopecks internally
payment_provider: "wayforpay"
support_channel: "@hirebot_support"
offer_link: "https://hirebot.pro/offer"
privacy_link: "https://hirebot.pro/privacy"
logo_url: "https://cdn.hirebot.pro/logo.png"
primary_color: "#1A73E8"
```

New brand = copy YAML + `WHITE_LABEL_CLIENT_ID=acme` env var + restart. **~5 minutes.**

### Tier 2 — DB-backed (opt-in, `WHITE_LABEL_ENABLED=true`)

Config stored in `business_config` table, editable via Dashboard without restart.
Cache TTL = 60s (Redis). Fallback to YAML on cache miss + DB error.

### Resolution order

```
ENV override → DB config (if enabled) → YAML file → platform defaults
```

## Consequences

### Positive
- New brand in 5 minutes without code change or release.
- DB-backed mode allows Dashboard self-service by tenant admins.
- Fallback chain prevents runtime errors if DB is temporarily unavailable.
- YAML configs are code-reviewed → no accidental mis-configuration in production.

### Negative
- DB-backed mode introduces eventual consistency (up to 60s cache TTL).
- Two config sources can diverge if YAML is updated without syncing DB.
- `tariff_amount` in YAML is `float` (UX convenience) — must be converted to kopecks at load time.

## References

- ADR-001: Multi-Tenant Architecture (white label is per-tenant, resolved by `tenant_id`).
- ADR-0025: Feature Flags as Kill-Switch (`WHITE_LABEL_ENABLED` is itself a feature flag).

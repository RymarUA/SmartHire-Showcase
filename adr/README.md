# Architecture Decision Records

All non-trivial architectural decisions in SmartHire are documented here.
New decisions follow `docs/adr/template.md` from the private repository.

## Index

| # | File | Decision | Status |
|---|------|----------|--------|
| 001 | [001_multi_tenant_architecture.md](001_multi_tenant_architecture.md) | Shared Schema + PostgreSQL RLS + FORCE RLS for tenant isolation | Accepted |
| 005 | [005_module_federation.md](005_module_federation.md) | `BaseModule` ABC + `ModuleRegistry` for plug-in business verticals | Accepted |
| 0014 | [0014_money_basis_points.md](0014_money_basis_points.md) | Integer kopecks + basis points; `float` banned in `core/payments/` | Accepted |
| 0019 | [0019_payment_idempotency.md](0019_payment_idempotency.md) | HMAC + Redis SETNX + daily reconciliation for exactly-once payments | Accepted |
| 0021 | [0021_white_label.md](0021_white_label.md) | YAML-first config with optional DB-backed dynamic overrides | Accepted |
| 0023 | [0023_frontend_backend_contract.md](0023_frontend_backend_contract.md) | Frontend/backend contract: OpenAPI, TanStack Query, httpOnly JWT | Accepted |
| 0025ff | [0025_feature_flags.md](0025_feature_flags.md) | Per-tenant feature flags as runtime kill-switch | Accepted |
| 0025pg | [0025_postgresql_partitioning.md](0025_postgresql_partitioning.md) | PostgreSQL table partitioning strategy for high-volume tables | Accepted |
| 0028 | [0028_zero_downtime_deployments.md](0028_zero_downtime_deployments.md) | Helm HPA+PDB + expand-contract migration discipline | Accepted |
| 0030 | [0030_multitenancy_hardening.md](0030_multitenancy_hardening.md) | Multi-tenancy hardening: RLS FORCE + `@tenant_scoped` + middleware | Accepted |
| 0032 | [0032_service_layer_enforcement.md](0032_service_layer_enforcement.md) | Headless service layer: handlers never import from `database/` | Accepted |
| 0048 | [0048_typed_dependency_injection.md](0048_typed_dependency_injection.md) | Typed DI on Dishka: explicit lifetimes, fail-closed tenant scopes; legacy container removed | Completed |
| 0069 | [0069_canonical_exception_hierarchy.md](0069_canonical_exception_hierarchy.md) | One class object per exception name; identity pinned across import paths | Accepted |
| 0070 | [0070_normalized_revenue_ledger.md](0070_normalized_revenue_ledger.md) | Single CTE as the only definition of "what counts as revenue" | Accepted |
| 0072 | [0072_e2e_tenant_isolation_model.md](0072_e2e_tenant_isolation_model.md) | E2E tenant isolation: decision space documented, owner-gated | Draft |
| 0074 | [0074_onboarding_proof_of_ownership.md](0074_onboarding_proof_of_ownership.md) | Challenge-nonce over webhook replaces `getUpdates` polling | Draft |

## Numbering Convention

Production numbering is continuous (`001`–`0075`+). Rough bands:

- `001`–`009`: Foundational architecture (tenancy, modules, data model)
- `0010`–`0019`: Data & storage decisions
- `0020`–`0029`: Integration & security
- `0030`–`0039`: Operational & deployment
- `0040`+: DI migration, domain layer, frontend topology, governance, revenue ledger

This showcase publishes a curated subset — the decisions that best explain how
the platform is designed and why.

## Template

New ADRs follow this structure:
1. **Context** — what problem forced this decision
2. **Decision** — what we chose and the key implementation
3. **Consequences** — positive and negative trade-offs
4. **References** — related ADRs and code files

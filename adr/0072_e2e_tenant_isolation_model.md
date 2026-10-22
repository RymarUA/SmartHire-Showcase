# ADR 0072: E2E Tenant-Isolation Model — how scenario state is separated across tenants

**Status:** Draft (decision owner-gated — see below)
**Date:** 2026-10-16
**Author:** SmartHire Architecture Team
**Related:** ADR 0030 (multitenancy hardening), ADR 0056 (three-path isolation)

## Context

The E2E orchestrator is single-tenant by construction: one bot token, one seeded
tenant, in-process queue workers for that tenant only. Between scenarios,
isolation is **global and destructive**, not namespaced: every table is TRUNCATEd
(except the keep-list), Redis logical DBs are flushed.

A green "N/N PASS" E2E run therefore proves **scenario correctness — but not
tenant isolation**. Existing coverage is real but lives on lower layers:
repository/service-predicate negatives, PostgreSQL RLS-enforced role properties,
a NOBYPASSRLS probe through the production pool path. None of them exercises
**two live tenants end-to-end** through the real
webhook → middleware → repository → Redis/queue → worker path.

Two hardening facts already landed with this draft:

- Cleanup is **fail-closed**: TRUNCATEs run inside one transaction (atomic
  rollback on failure), Redis flush retries then raises, and the final teardown
  forces a non-zero exit instead of masking an in-flight exception. A failed
  reset can no longer leave a dirty scenario silently green.
- A census of **~13 process-global caches** (tenant routing, feature flags,
  white-label config, payment provider factory, …) documented which caches the
  reset path must clear — most are TTL-bounded (~300 s), so residual risk is
  stale-state bleed between back-to-back scenarios, not permanent contamination.

## Decision

**PENDING — owner decision required.** This draft deliberately does not select an
isolation model. Recording a chosen design before the owner rules would be
fiction; the alternatives below are the decision space, not a recommendation.

Decision criteria: blast radius of a cleanup failure; production fidelity
(exercise the same tenant-resolution paths production uses); plumbing cost of a
second live tenant (own token, seed, webhook route, worker); determinism
(scenario N must not observe scenario N−1 through any layer); CI time budget.

| Alternative | Pros | Cons |
|---|---|---|
| Two parallel tenants + targeted cleanup | Highest production fidelity — same code paths | Needs a real second bot token/route/worker; hardest to make deterministic |
| Schema-per-scenario via `search_path` | DB isolation is structural | Diverges from shared-table+RLS production default; doesn't cover Redis/queues |
| Redis key prefixes + tenant-scoped queues | Covers non-DB state; matches the key-prefix red line | Prefix discipline is convention, not enforcement |
| Disposable database per scenario | Strongest DB isolation; failed cleanup fails loudly | Slowest — a migration run per scenario inside a PR budget is questionable |

A realistic design is likely a composition (two-tenant fidelity + Redis
namespacing + fail-closed cleanup), not a pure winner — which is exactly why the
choice is owner-gated rather than implied.

## Consequences

- **Positive (of the process):** the gap is named and scoped instead of assumed
  away; cleanup failures are already loud; the cache census becomes a load-bearing
  part of the harness contract.
- **Negative:** a second tenant doubles part of the fixture surface and lengthens
  the run; whichever model wins, the cache-reset path must grow to the full census.

## Why this ADR is public in draft form

It documents **how decisions are made**, not just what was decided: the decision
space with trade-offs is written down, the owner gate is explicit, and no design
is recorded as "chosen" before it actually is. Architecture decisions are
owner-gated — AI tooling assists analysis but does not select the model.

## References

- Multitenancy hardening: ADR 0030
- Schema-per-tenant enterprise isolation: ADR 0035
- Three-path tenant isolation: ADR 0056

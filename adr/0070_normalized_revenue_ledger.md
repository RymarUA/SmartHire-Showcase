# ADR 0070: Normalized Revenue Ledger — one CTE as the single definition of revenue

**Status:** Active
**Date:** 2026-10-15
**Author:** SmartHire Architecture Team

## Context

Two tables carry money, and they disagree:

| | `payments` (B2C anketa/manual) | `billing_payments` (subscription/onboarding SSOT) |
|---|---|---|
| Paid status | three legacy spellings: `'paid'`, `'success'`, `'settled'` | `'paid'` |
| Amount column | INTEGER | BIGINT |
| Dimensions | `user_id`, `subscription_id`, `provider` | `tenant_id`, `provider_order_id`, billing period — **no** `user_id`/`plan_id` |

Six revenue surfaces (MRR history, revenue stats, billing dashboard, business
metrics, revenue snapshots) queried `payments` alone. Every hryvnia of
subscription/onboarding revenue written to `billing_payments` was **invisible**
to MRR, dashboards, and platform analytics — a paid onboarding webhook landed in
one table while every dashboard read the other. Each surface also encoded its own
paid-status predicate, undercounting even the B2C side.

## Decision

A single shared SQL fragment — `REVENUE_LEDGER_CTE` — is the **only** place that
defines "what counts as revenue":

```sql
WITH revenue_ledger AS (
    SELECT tenant_id, amount::BIGINT AS amount, currency, created_at
    FROM payments
    WHERE status IN ('paid', 'success', 'settled')
    UNION ALL
    SELECT tenant_id, amount, currency, created_at
    FROM billing_payments
    WHERE status = 'paid'
)
```

- Consumers prepend the CTE and aggregate `FROM revenue_ledger`. The fragment is
  a static literal (no interpolation) per the SQL-construction rules (ADR 0054).
- **Currency rule:** the ledger emits `currency`; consumers must never `SUM(amount)`
  across currencies. Scalar surfaces bind the settlement currency (`UAH`) and
  document themselves as settlement-denominated; series surfaces may
  `GROUP BY currency`. Filtering ≠ conversion — non-settlement rows are excluded,
  not exchanged.
- **Excluded by design:** per-user and per-plan aggregations stay on `payments`
  alone — the SSOT ledger does not carry those dimensions, and inventing them
  would be fiction.

## Consequences

- **Positive:** onboarding/subscription revenue is visible on every revenue
  surface; adding a future paid-status spelling is a one-line change in one
  reviewed fragment instead of six call sites; `INTEGER` amounts are cast to
  `BIGINT` at the union boundary — no overflow as volumes grow. Shape pins in
  tests lock the union, the status sets, and the currency column.
- **Negative:** refunded rows are excluded whole — revenue is gross of partial
  refunds (documented simplification); the union adds a second table scan to six
  queries, all dashboard/snapshot paths, not hot request paths.
- **Neutral:** the settlement currency is a module constant, not runtime config —
  changing it is a deliberate code change affecting all surfaces atomically.

## Key Pattern

```python
# Every revenue surface emits the same fragment — one definition of "revenue"
query = with_revenue_ledger("""
    SELECT date_trunc('month', created_at) AS month,
           SUM(amount) AS revenue
    FROM revenue_ledger
    WHERE currency = $1
    GROUP BY 1
""").bind(SETTLEMENT_CURRENCY)
```

## References

- SQL construction rules (literal fragments, no interpolation): ADR 0054
- Exception hierarchy (revenue errors): ADR 0069

# ADR-0014: Money as Integer Kopecks + Basis Points

**Status:** Accepted  
**Date:** 2024-11-03  
**Last reviewed:** 2026-04-19

## Context

Early prototypes used `float` for payment amounts. A quarterly reconciliation found a 1-kopeck
discrepancy on 847 transactions caused by `float` precision drift (`4.01 * 100 = 401.00000000000006`).
Commission calculations using percentage multipliers compounded the error.

## Decision

1. **All monetary amounts stored and computed as integer kopecks** (`amount_kopecks: int`).
2. **Percentages expressed as basis points** (`commission_bp: int` where 250 = 2.5%).
3. **`Decimal` used only at system boundaries** (JSON parsing, display formatting).
4. **Custom ruff rule** bans `float` annotations in `core/payments/` at pre-commit.

```python
# Wrong — banned by ruff rule PL-MONEY-001
price: float = 49.99

# Correct
price_kopecks: int = 4999
commission_bp: int = 150  # 1.5%

# Boundary conversion (only here)
price_kopecks = int(Decimal("49.99") * 100)
```

## Consequences

### Positive
- Zero rounding errors in 18 months of production after migration.
- Quarterly reconciliation: 0 kopeck discrepancy since ADR adoption.
- Basis-point commissions are exact integer arithmetic: `amount * bp // 10_000`.
- `hypothesis`-generated property tests cover 10 000+ amount combinations.

### Negative
- All display code must convert kopecks → UAH string at the last moment.
- Onboarding new developers requires explaining the convention.
- YAML white-label configs still accept `float` for UX; conversion happens at config load time.

## Migration

Existing `NUMERIC(10,2)` columns converted to `BIGINT` via expand-contract (ADR-0028):
- Expand: add `amount_kopecks BIGINT`, backfill `= ROUND(amount * 100)`.
- Contract: drop `amount` column after 2 releases.

## References

- `code/money.py` — `to_kopecks()`, `validate_amount()`, `compare_amounts()`.
- ADR-0019: Payment Idempotency (reconciliation depends on integer comparison).
- ADR-0028: Zero-Downtime Deployments (column migration strategy).

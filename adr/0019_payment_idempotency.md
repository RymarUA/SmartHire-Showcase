# ADR-0019: Payment Webhook Idempotency + Daily Reconciliation

**Status:** Accepted  
**Date:** 2025-01-17  
**Last reviewed:** 2026-04-19

## Context

WayForPay and LiqPay do not guarantee exactly-once webhook delivery. During a network partition
incident in Q4 2024, 23 webhooks were delivered 2–4 times within 30 seconds. Without idempotency,
this would have created duplicate payment records and double-activated subscriptions.

Additionally, webhook delivery can fail entirely (provider retries exhausted). A payment can be
"real" in the bank but "pending" in our DB.

## Decision

Three complementary mechanisms — any single one is insufficient:

### 1. HMAC Signature + IP Allowlist

```python
def validate_wayforpay_signature(body: bytes, secret: str, received_hmac: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_hmac)
```

IP allowlist enforced at Nginx level before the app sees the request.

### 2. Redis Idempotency Key (SETNX, TTL 24h)

```python
key = f"webhook:processed:{provider}:{event_id}"
acquired = await redis.set(key, "1", nx=True, ex=86_400)
if not acquired:
    return  # duplicate — silently discard
```

`SETNX` is atomic; concurrent duplicate webhooks race and exactly one wins.

### 3. Daily Reconciliation (APScheduler, 03:00 UTC)

- Fetches all transactions from provider API for the past 24h.
- Compares with DB `payments` table (integer kopeck comparison).
- Generates Excel report (3 sheets: Payments / Anketas / Discrepancies).
- Sends report to operator Telegram channel.
- `/audit` command triggers ad-hoc reconciliation for the last 24h.

Webhook is a fast-path optimization. Reconciliation is the source of truth.

## Consequences

### Positive
- Zero duplicate payments in production since adoption.
- Missed webhooks are caught within 24h max (next reconciliation cycle).
- Excel report gives operators full audit trail without DB access.

### Negative
- Redis TTL means idempotency window is 24h; duplicate webhooks after 24h would reprocess
  (acceptable: providers retry within hours, not days).
- Reconciliation job adds ~15s load at 03:00 UTC; mitigated by `FOR UPDATE SKIP LOCKED`.

## References

- `code/webhook_validator.py` — HMAC validation excerpt.
- ADR-0014: Money as Basis Points (reconciliation comparison uses integer kopecks).
- ADR-001: Multi-Tenant Architecture (reconciliation is tenant-scoped).

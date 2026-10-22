# ADR 0074: Onboarding Proof-of-Ownership — webhook challenge-nonce

**Status:** Draft (implementation pending)
**Date:** 2026-10-19
**Author:** SmartHire Architecture Team
**Related:** ADR 0030 (multitenancy hardening), ADR 0073 (order-id tenant embedding)

## Context

During onboarding, a new tenant registers **their own bot token**. Before the
platform can act as that bot, ownership must be proven. Today the proof is
*polling `getUpdates`* for a `/verify` message the registrant sends to their
candidate bot.

Costs of the polling design:

1. **Worker hold** — each verification occupies a request worker for up to ~30 s
   of network polling.
2. **`getUpdates` exclusivity** — polling steals the update stream: if a webhook
   or another poller owns it, Telegram answers `Conflict`. A webhook-configured
   bot cannot be verified by polling at all.
3. **Weakest-link proof** — "whoever could `getUpdates` saw a `/verify`"
   authenticates token possession, not a fresh, challenge-bound act by this
   registrant at this moment.

## Decision

Replace polling with a **challenge-nonce over the webhook path**:

1. Server mints a single-use nonce (TTL ~10 min, Redis, bound to
   `{token_fingerprint, user_id}`).
2. The registrant points the candidate bot's webhook at the provided endpoint
   (or the server sets it via `setWebhook` with a minted secret token) and sends
   `/verify <nonce>` — or the nonce arrives as the webhook
   `X-Telegram-Bot-Api-Secret-Token` header on the first delivered update.
3. Server consumes the nonce atomically (`GETDEL`/Lua) on first match:
   single-use, single-tenant, non-replayable.
4. The polling fallback stays during migration for tokens that cannot take a
   webhook, then retires.

## Consequences

- **Positive:** frees the request worker (verification becomes webhook-bound,
  not ~30 s of held polling); fresh, challenge-bound proof instead of "saw any
  `/verify` in the stream"; removes the `getUpdates` Conflict class for
  webhook-capable bots.
- **Negative:** requires the candidate bot to accept a webhook — polling-only
  tokens need the retained fallback; one more Redis-backed nonce lifecycle
  (mint/consume/expire) to test.
- **Neutral:** verify endpoints stay in the strict rate-limit tier regardless.

## Key Pattern

```python
# Mint: single-use, bound to the registrant, short TTL
nonce = await redis.mint(
    key=f"onboarding:pow:{token_fingerprint}:{user_id}",
    ttl=timedelta(minutes=10),
)

# Consume: atomic GETDEL — second replay finds nothing
consumed = await redis.consume_once(key)  # Lua: GET + DEL in one step
if not consumed:
    raise OwnershipChallengeExpired()
```

## References

- Multitenancy hardening: ADR 0030
- Per-prefix tenant embedding for payment order ids: ADR 0073

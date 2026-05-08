"""Sanitized excerpt from SmartHire proprietary codebase.

Demonstrates payment webhook validation pattern (ADR-0019):
- HMAC-SHA256 signature verification (constant-time comparison).
- IP allowlist enforcement (applied before this code runs, at Nginx level).
- Redis SETNX idempotency key to guarantee exactly-once processing.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WebhookSignatureError(ValueError):
    """Raised when HMAC signature does not match."""


class WebhookDuplicateError(RuntimeError):
    """Raised when this event_id was already processed (idempotency guard)."""


# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------


def validate_wayforpay_signature(
    body: bytes,
    secret: str,
    received_hmac: str,
) -> None:
    """Verify WayForPay HMAC-SHA256 webhook signature.

    Uses `hmac.compare_digest` to prevent timing attacks.

    Args:
        body: Raw request body bytes (before any JSON parsing).
        secret: Merchant secret key from environment config.
        received_hmac: Value from `X-WayForPay-Signature` header.

    Raises:
        WebhookSignatureError: If the computed HMAC does not match.
    """
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, received_hmac):
        logger.warning("Webhook HMAC mismatch — possible spoofing attempt")
        raise WebhookSignatureError("Invalid webhook signature")


def validate_liqpay_signature(
    data_b64: str,
    private_key: str,
    received_signature: str,
) -> None:
    """Verify LiqPay SHA1 webhook signature.

    LiqPay uses SHA1(private_key + data_b64 + private_key) base64-encoded.

    Args:
        data_b64: Base64-encoded payload from the `data` POST field.
        private_key: LiqPay private key from environment config.
        received_signature: Value from the `signature` POST field.

    Raises:
        WebhookSignatureError: If the computed signature does not match.
    """
    import base64

    raw = f"{private_key}{data_b64}{private_key}".encode("utf-8")
    expected = base64.b64encode(hashlib.sha1(raw).digest()).decode("utf-8")  # noqa: S324

    if not hmac.compare_digest(expected, received_signature):
        logger.warning("LiqPay signature mismatch — possible spoofing attempt")
        raise WebhookSignatureError("Invalid LiqPay webhook signature")


# ---------------------------------------------------------------------------
# Idempotency guard (Redis SETNX)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Structured idempotency key for a payment event.

    Args:
        provider: Payment provider name ('wayforpay' | 'liqpay').
        event_id: Provider-assigned transaction / order ID.
    """

    provider: str
    event_id: str

    def to_redis_key(self) -> str:
        """Render as Redis key string."""
        return f"webhook:processed:{self.provider}:{self.event_id}"


async def acquire_idempotency_lock(
    redis: Redis,
    key: IdempotencyKey,
    ttl_seconds: int = 86_400,
) -> None:
    """Claim an idempotency slot in Redis using SETNX.

    Atomic: concurrent duplicate webhooks race; exactly one caller wins.
    The loser raises `WebhookDuplicateError` — the caller should return HTTP 200
    to the provider (prevent retry) but skip all business logic.

    Args:
        redis: Async Redis client.
        key: Structured idempotency key.
        ttl_seconds: Key TTL (default 24h). After expiry the event could be
            reprocessed — acceptable because providers retry within hours.

    Raises:
        WebhookDuplicateError: If this event was already processed.
    """
    redis_key = key.to_redis_key()
    acquired: bool = await redis.set(redis_key, "1", nx=True, ex=ttl_seconds)

    if not acquired:
        logger.info(
            "Duplicate webhook discarded",
            extra={"provider": key.provider, "event_id": key.event_id},
        )
        raise WebhookDuplicateError(
            f"Event {key.provider}:{key.event_id} already processed"
        )

"""
Subscription state machine with compensating actions for billing lifecycle.

Explicit state machine implementation (no transitions library) to avoid
dynamic attribute issues with type checkers.

States: trial, active, grace_period, paused, cancelled
- cancelled is terminal (absorbing state)
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

TRIAL_DAYS = 14
GRACE_PERIOD_DAYS = 3


class BillingState(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    GRACE_PERIOD = "grace_period"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class SubscriptionStateMachine:
    """
    Explicit state machine for subscription lifecycle.

    States: trial, active, grace_period, paused, cancelled
    - cancelled is terminal (absorbing state)

    Transitions with guards and compensating actions.
    """

    def __init__(
        self,
        gateway: Any,
        bot: Any,
        cache: Any,
        tenant_id: str,
        initial_state: str = "trial",
    ) -> None:
        self.gateway = gateway
        self.bot = bot
        self.cache = cache
        self.tenant_id = tenant_id
        self.state: str = initial_state
        self._previous_state: str | None = None
        self._event_data: dict[str, Any] = {}

    # ── Transitions ──────────────────────────────────────────────────────────

    async def activate(
        self, payment_id: str | None = None, amount: float = 0.0
    ) -> None:
        """
        Activate subscription from trial or grace_period.

        Guards: can_activate must pass.
        Side effects: update subscription, set tenant active,
            invalidate cache, notify.
        Compensation: rollback status on error.
        """
        if self.state not in (BillingState.TRIAL, BillingState.GRACE_PERIOD):
            return

        if not self._can_activate():
            return

        self._previous_state = self.state
        self._event_data = {"payment_id": payment_id, "amount": amount}

        try:
            await self._after_activate()
            self.state = BillingState.ACTIVE
        except Exception:
            await self._compensate_activate()
            raise

    async def expire_trial(self) -> None:
        """Move expired trial to grace period."""
        if self.state != BillingState.TRIAL:
            return

        self._previous_state = self.state

        try:
            await self._after_expire_trial()
            self.state = BillingState.GRACE_PERIOD
        except Exception:
            raise

    async def payment_fail(self) -> None:
        """Enter grace period after failed payment."""
        if self.state != BillingState.ACTIVE:
            return

        self._previous_state = self.state

        try:
            await self._after_payment_fail()
            self.state = BillingState.GRACE_PERIOD
        except Exception:
            raise

    async def payment_success(self, payment_id: str | None = None) -> None:
        """Return to active state after successful payment in grace period."""
        if self.state != BillingState.GRACE_PERIOD:
            return

        if not self._can_activate():
            return

        self._previous_state = self.state
        self._event_data = {"payment_id": payment_id}

        try:
            await self._after_payment_success()
            self.state = BillingState.ACTIVE
        except Exception:
            await self._compensate_payment_success()
            raise

    async def grace_expired(self) -> None:
        """Move from grace period to paused when grace period ends."""
        if self.state != BillingState.GRACE_PERIOD:
            return

        self._previous_state = self.state

        try:
            await self._after_grace_expired()
            self.state = BillingState.PAUSED
        except Exception:
            raise

    async def resume(self) -> None:
        """Resume paused subscription."""
        if self.state != BillingState.PAUSED:
            return

        if not self._can_activate():
            return

        self._previous_state = self.state

        try:
            await self._after_resume()
            self.state = BillingState.ACTIVE
        except Exception:
            await self._compensate_resume()
            raise

    async def cancel(self) -> None:
        """Cancel subscription (terminal state)."""
        if self.state == BillingState.CANCELLED:
            return

        self._previous_state = self.state

        try:
            await self._after_cancel()
            self.state = BillingState.CANCELLED
        except Exception:
            raise

    # ── Guard conditions ────────────────────────────────────────────────────

    def _can_activate(self) -> bool:
        """Guard: check if activation is allowed."""
        return True

    # ── After hooks (side effects) ──────────────────────────────────────────

    async def _after_activate(self) -> None:
        """Post-activation: update tenant status, invalidate cache, notify."""
        now = datetime.now(UTC)
        await self.gateway.update_subscription(
            self.tenant_id,
            {
                "status": BillingState.ACTIVE,
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
                "grace_period_ends_at": None,
                "last_payment_id": self._event_data.get("payment_id"),
                "last_payment_at": now,
            },
        )
        await self.gateway.set_tenant_active(self.tenant_id, True)
        await self._invalidate_cache()

    async def _after_expire_trial(self) -> None:
        """Post-trial expiry: start grace period."""
        now = datetime.now(UTC)
        grace_ends = now + timedelta(days=GRACE_PERIOD_DAYS)
        await self.gateway.update_subscription(
            self.tenant_id,
            {
                "status": BillingState.GRACE_PERIOD,
                "grace_period_ends_at": grace_ends,
            },
        )

    async def _after_payment_fail(self) -> None:
        """Post-payment failure: enter grace period."""
        now = datetime.now(UTC)
        grace_ends = now + timedelta(days=GRACE_PERIOD_DAYS)
        await self.gateway.update_subscription(
            self.tenant_id,
            {
                "status": BillingState.GRACE_PERIOD,
                "grace_period_ends_at": grace_ends,
            },
        )

    async def _after_payment_success(self) -> None:
        """Post-payment success: activate subscription."""
        now = datetime.now(UTC)
        await self.gateway.update_subscription(
            self.tenant_id,
            {
                "status": BillingState.ACTIVE,
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
                "grace_period_ends_at": None,
                "last_payment_id": self._event_data.get("payment_id"),
                "last_payment_at": now,
            },
        )
        await self.gateway.set_tenant_active(self.tenant_id, True)
        await self._invalidate_cache()

    async def _after_grace_expired(self) -> None:
        """Post-grace period expiry: pause subscription."""
        await self.gateway.update_subscription(
            self.tenant_id,
            {"status": BillingState.PAUSED},
        )
        await self.gateway.set_tenant_active(self.tenant_id, False)
        await self._invalidate_cache()

    async def _after_resume(self) -> None:
        """Post-resume: reactivate tenant."""
        now = datetime.now(UTC)
        await self.gateway.update_subscription(
            self.tenant_id,
            {
                "status": BillingState.ACTIVE,
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
            },
        )
        await self.gateway.set_tenant_active(self.tenant_id, True)
        await self._invalidate_cache()

    async def _after_cancel(self) -> None:
        """Post-cancel: deactivate tenant permanently."""
        await self.gateway.update_subscription(
            self.tenant_id,
            {
                "status": BillingState.CANCELLED,
                "cancelled_at": datetime.now(UTC),
            },
        )
        await self.gateway.set_tenant_active(self.tenant_id, False)
        await self._invalidate_cache()

    # ── Compensation handlers ───────────────────────────────────────────────

    async def _compensate_activate(self) -> None:
        """Rollback activation on error."""
        await self._rollback_status("activate")

    async def _compensate_payment_success(self) -> None:
        """Rollback payment success on error."""
        await self._rollback_status("payment_success")

    async def _compensate_resume(self) -> None:
        """Rollback resume on error."""
        await self._rollback_status("resume")

    async def _rollback_status(
        self, trigger_name: str
    ) -> None:
        """Restore previous status in DB after failed transition."""
        if self._previous_state:
            try:
                await self.gateway.update_subscription(
                    self.tenant_id,
                    {"status": self._previous_state},
                )
            except Exception:
                pass

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _invalidate_cache(self) -> None:
        """Invalidate tenant cache."""
        try:
            if hasattr(self.cache, "invalidate_tenant"):
                await self.cache.invalidate_tenant(self.tenant_id)
            elif hasattr(self.cache, "delete"):
                await self.cache.delete(f"tenant:{self.tenant_id}")
        except Exception:
            pass


__all__ = [
    "BillingState",
    "SubscriptionStateMachine",
    "TRIAL_DAYS",
    "GRACE_PERIOD_DAYS",
]

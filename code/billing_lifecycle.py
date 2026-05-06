"""
Billing lifecycle — central subscription status transitions.

All status changes MUST go through BillingLifecycle.
Never update tenant_subscriptions directly from handlers.

Uses explicit state machine with compensating actions.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from core.billing.state_machine import BillingState, SubscriptionStateMachine

TRIAL_DAYS = 14
GRACE_PERIOD_DAYS = 3
REMINDER_DAYS_BEFORE = 3


class BillingLifecycle:
    """
    Central logic for subscription status transitions.

    Delegates to SubscriptionStateMachine for explicit state management
    with compensating actions on failure.

    Args:
        gateway: billing gateway
        bot: aiogram Bot instance for notifications
        cache: cache instance for tenant invalidation
    """

    def __init__(self, gateway: Any, bot: Any, cache: Any) -> None:
        self.gateway = gateway
        self.bot = bot
        self.cache = cache

    async def create_trial(
        self, tenant_id: str, plan_id: str
    ) -> dict[str, Any]:
        """Create a trial subscription on tenant registration."""
        now = datetime.now(UTC)
        trial_ends = now + timedelta(days=TRIAL_DAYS)
        subscription: dict[str, Any] = await self.gateway.create_subscription(
            {
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "status": BillingState.TRIAL,
                "trial_ends_at": trial_ends,
                "current_period_start": now,
                "current_period_end": trial_ends,
            }
        )
        return subscription

    async def activate(
        self, tenant_id: str, payment_id: str, amount: float
    ) -> None:
        """Activate subscription after successful payment."""
        machine = SubscriptionStateMachine(
            gateway=self.gateway,
            bot=self.bot,
            cache=self.cache,
            tenant_id=tenant_id,
            initial_state=BillingState.TRIAL,
        )
        await machine.activate(
            payment_id=payment_id, amount=amount
        )

    async def start_grace_period(self, tenant_id: str) -> None:
        """Start grace period on failed payment."""
        machine = SubscriptionStateMachine(
            gateway=self.gateway,
            bot=self.bot,
            cache=self.cache,
            tenant_id=tenant_id,
            initial_state=BillingState.ACTIVE,
        )
        await machine.payment_fail()

    async def pause(self, tenant_id: str, reason: str = "") -> None:
        """Pause bot after grace period exhausted."""
        machine = SubscriptionStateMachine(
            gateway=self.gateway,
            bot=self.bot,
            cache=self.cache,
            tenant_id=tenant_id,
            initial_state=BillingState.GRACE_PERIOD,
        )
        await machine.grace_expired()

    async def resume(self, tenant_id: str) -> None:
        """Resume paused subscription."""
        machine = SubscriptionStateMachine(
            gateway=self.gateway,
            bot=self.bot,
            cache=self.cache,
            tenant_id=tenant_id,
            initial_state=BillingState.PAUSED,
        )
        await machine.resume()

    async def cancel(self, tenant_id: str) -> None:
        """Cancel subscription."""
        subscription = await self.gateway.get_subscription(tenant_id)
        current_state = (
            subscription.get("status", BillingState.TRIAL)
            if subscription
            else BillingState.TRIAL
        )
        machine = SubscriptionStateMachine(
            gateway=self.gateway,
            bot=self.bot,
            cache=self.cache,
            tenant_id=tenant_id,
            initial_state=str(current_state),
        )
        await machine.cancel()

    async def expire_trial(self, tenant_id: str) -> None:
        """Move expired trial to grace period."""
        machine = SubscriptionStateMachine(
            gateway=self.gateway,
            bot=self.bot,
            cache=self.cache,
            tenant_id=tenant_id,
            initial_state=BillingState.TRIAL,
        )
        await machine.expire_trial()


__all__ = ["BillingLifecycle", "TRIAL_DAYS", "GRACE_PERIOD_DAYS"]

"""Access policy derived from the validated billing state (scope §25). No Stripe calls here:
the webhooks keep ``Subscription`` up to date and this only reads it."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.billing.models import Subscription

ACTIVE_STATUSES = {"trialing", "active", "past_due"}  # past_due: Stripe is still retrying


def entitled(sub: Subscription | None, *, now: datetime | None = None) -> bool:
    if sub is None:
        return False
    now = now or datetime.now(UTC)
    if sub.kind == "vip":
        if sub.vip_until and sub.vip_until > now:
            return True
        # after the VIP period: "then_charge" behaves like a normal subscription; in the
        # invite-only mode the renewal follows the platform rules (not defined yet) → no access
        return sub.vip_after == "then_charge" and sub.status in ACTIVE_STATUSES
    if sub.status in ACTIVE_STATUSES:
        return True
    # canceled during the trial (or at period end): keeps access until the paid/free time ends
    end = sub.trial_end if sub.status == "canceled" and sub.trial_end else sub.current_period_end
    return bool(sub.status == "canceled" and end and end > now)


def state_label(sub: Subscription | None, *, now: datetime | None = None) -> str:
    """trial | active | vip | past_due | canceled | expired | none — for the UI banner."""
    if sub is None:
        return "none"
    now = now or datetime.now(UTC)
    if sub.kind == "vip" and sub.vip_until and sub.vip_until > now:
        return "vip"
    if sub.status == "trialing":
        return "trial"
    if sub.status == "past_due":
        return "past_due"
    if sub.status == "canceled":
        return "canceled" if entitled(sub, now=now) else "expired"
    if sub.status == "active":
        return "active"
    return "expired"

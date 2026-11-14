"""Local projection of Stripe (scope §25). Stripe is the source of truth; these rows are
reconciled from webhooks and a periodic check. Never store a card number or CVV."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

PRICES_CENTS = {"monthly": 25_000, "annual": 250_000}


class Subscription(IdMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True
    )
    # monthly | annual (what is charged after the trial / the VIP plan)
    plan: Mapped[str] = mapped_column(String(10), nullable=False, default="monthly")
    # standard (7-day trial) | vip (invited, free until vip_until)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="standard")
    # trialing | active | past_due | canceled | unpaid | incomplete
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="incomplete")
    stripe_customer_id: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    stripe_subscription_id: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    card_brand: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    card_last4: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    card_exp: Mapped[str] = mapped_column(String(7), nullable=False, default="")
    trial_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # VIP plan: free until this moment; in "invite only" mode nothing is charged after it
    vip_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # invite_only (renewal by the platform rules) | then_charge (charge `plan` after vip_until)
    vip_after: Mapped[str] = mapped_column(String(12), nullable=False, default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    stripe_invoice_id: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # draft | open | paid | uncollectible | void
    status: Mapped[str] = mapped_column(String(14), nullable=False, default="open")
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hosted_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class Purchase(IdMixin, TimestampMixin, Base):
    """One-off payments by Stripe Checkout: Brilhar packages, mentorship, paid events."""

    __tablename__ = "purchases"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # boost | mentorship | event
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    ref: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # pending | paid | failed | refunded | canceled
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    stripe_session_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class StripeEvent(Base):
    """Every webhook received, keyed by the Stripe event id (idempotency, §25)."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")


class TrialClaim(Base):
    """A CNPJ gets one free trial, ever, whatever user or account asks again (§2.1)."""

    __tablename__ = "trial_claims"

    cnpj: Mapped[str] = mapped_column(String(14), primary_key=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

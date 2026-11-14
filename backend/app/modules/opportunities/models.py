"""Commercial opportunities with their own funnel (scope §12, §15)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

STAGES = ("new", "contact", "qualification", "negotiation", "proposal", "won", "lost")
OPP_ORIGINS = ("MUTUAL_LIKE", "AI_RECOMMENDATION", "DIRECT", "EVENT", "REFERRAL", "MANUAL")


class Opportunity(IdMixin, TimestampMixin, Base):
    __tablename__ = "opportunities"

    number: Mapped[int] = mapped_column(BigInteger, Identity(start=100), unique=True)
    # buy_sell (buyer and seller) | partnership (the two companies in the buyer/seller slots)
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default="buy_sell")
    buyer_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    seller_org_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    created_by_org_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("matches.id", ondelete="SET NULL")
    )
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="MANUAL")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    product: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    compat: Mapped[int | None] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(14), nullable=False, default="new")
    value_estimate_cents: Mapped[int | None] = mapped_column(BigInteger)
    next_action: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # {org_id: user_id}: each company picks its own responsible person
    owners: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    history: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    closed_value_cents: Mapped[int | None] = mapped_column(BigInteger)
    # the deal counts in "negócios efetivados" only when both companies confirmed (§15)
    close_confirmed_by: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class OpportunityNote(IdMixin, TimestampMixin, Base):
    """Private notes of one company about an opportunity; the other side never sees them."""

    __tablename__ = "opportunity_notes"
    __table_args__ = (UniqueConstraint("opportunity_id", "org_id", name="uq_opp_notes"),)

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")

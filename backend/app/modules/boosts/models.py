"""Brilhar na Rede (scope §2.2): paid exposure in the sponsored slots, with its own numbers.
A boost never changes the compatibility the matching computes."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

PACKAGES = {1: 3_900, 10: 29_900, 30: 79_900}  # days -> price in cents


class BoostCampaign(IdMixin, TimestampMixin, Base):
    __tablename__ = "boost_campaigns"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="SET NULL")
    )
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # pending (not paid) | active | finished | canceled
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")


class OrgDayStat(IdMixin, Base):
    """Daily counters per organization: card impressions (organic and sponsored), profile
    visits, likes received, connections and opportunities. Feeds Brilhar and the dashboard."""

    __tablename__ = "org_day_stats"
    __table_args__ = (UniqueConstraint("org_id", "day", name="uq_org_day_stats"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impressions_sponsored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profile_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    likes_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    connections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opportunities: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

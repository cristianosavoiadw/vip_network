"""Reciprocal interest between two organizations (scope §9, §10.6).

One row per pair (``org_low_id`` < ``org_high_id`` as strings). ``kind``/``status`` follow
``matches/rules.py``: buy×sell is a commercial match, part×part a partnership match, sell×sell
and buy×buy only a mutual interest.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

MATCH_STATUSES = (
    "MUTUAL_INTEREST",
    "MATCH_CONFIRMED",
    "CONNECTION_ACCEPTED",
    "IN_CONVERSATION",
    "ARCHIVED",
    "BLOCKED",
)
ORIGINS = (
    "MUTUAL_LIKE",
    "AI_RECOMMENDATION",
    "MANUAL_CONNECTION",
    "EVENT_CONNECTION",
    "STRATEGIC_MATCH",
)


class Match(IdMixin, TimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("org_low_id", "org_high_id", name="uq_matches_pair"),)

    org_low_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    org_high_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # commercial | partnership | mutual_sell | mutual_buy | relationship
    kind: Mapped[str] = mapped_column(String(14), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="MUTUAL_LIKE")
    buyer_org_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    seller_org_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    product: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score: Mapped[int | None] = mapped_column(Integer)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # users who already saw the "É MATCH!" modal (shown once per user, §9.2)
    seen_user_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

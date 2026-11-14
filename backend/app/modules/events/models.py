"""Business events and dinners with registration, waitlist and QR check-in (scope §16)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Event(IdMixin, TimestampMixin, Base):
    __tablename__ = "events"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    # jantar | rodada | cafe | encontro
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default="jantar")
    city: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(2), nullable=False, default="")
    place: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    image_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # draft | published | canceled
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="published")


class EventRegistration(IdMixin, TimestampMixin, Base):
    __tablename__ = "event_registrations"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_reg_user"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # confirmed | waitlist | canceled
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="confirmed")
    checkin_token: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rating: Mapped[int | None] = mapped_column(Integer)

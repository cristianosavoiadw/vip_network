"""Executive mentorship (scope §17). Confidential: never read by discovery or matching."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Mentor(IdMixin, TimestampMixin, Base):
    __tablename__ = "mentors"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    headline: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    photo_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    is_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MentorshipPlan(IdMixin, TimestampMixin, Base):
    __tablename__ = "mentorship_plans"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    mentor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("mentors.id", ondelete="SET NULL")
    )
    # pending (checkout open) | active | ended | canceled
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    sessions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1_500_000)
    diagnosis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    strategic_plan: Mapped[str] = mapped_column(Text, nullable=False, default="")
    goals: Mapped[str] = mapped_column(Text, nullable=False, default="")


class MentorshipSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "mentorship_sessions"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("mentorship_plans.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    topic: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    # requested | scheduled | done | canceled
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="requested")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class MentorshipDocument(IdMixin, TimestampMixin, Base):
    __tablename__ = "mentorship_documents"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("mentorship_plans.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(400), nullable=False, default="")

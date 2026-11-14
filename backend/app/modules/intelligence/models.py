"""Market reports and the recommendation cards of Visão Geral (scope §10, §18)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

RECOMMENDATION_KINDS = ("supplier", "buyer", "economy", "partner", "solution", "event")


class MarketReport(IdMixin, TimestampMixin, Base):
    __tablename__ = "market_reports"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # queued | running | ready | failed
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="queued")
    # {"sections": [{"key", "title", "confidence", "body", "items": [...]}], "sources": [...]}
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Recommendation(IdMixin, TimestampMixin, Base):
    """One card for one organization. Never exposes another company's private purchases:
    ``body`` is written for the receiving company only."""

    __tablename__ = "recommendations"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    target_org_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score: Mapped[int | None] = mapped_column(Integer)
    # savings math, offer ids, etc. — for the receiving org only
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # local (rule-based) | weos
    origin: Mapped[str] = mapped_column(String(10), nullable=False, default="local")
    # new | dismissed | acted
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="new")

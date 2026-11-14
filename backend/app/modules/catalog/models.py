"""The two catalogs of a company (scope §6): what it sells (public) and what it buys (private)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Offer(IdMixin, TimestampMixin, Base):
    __tablename__ = "offers"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="product")  # | service
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    specs: Mapped[str] = mapped_column(Text, nullable=False, default="")
    images: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    price_cents: Mapped[int | None] = mapped_column(BigInteger)
    price_on_request: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    min_order: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    conditions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    coverage: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    availability: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    # draft | published | paused
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="published")


class PurchaseNeed(IdMixin, TimestampMixin, Base):
    """Private by default. ``visibility=published`` exposes only name/category/spec/region
    (never price paid, current supplier or volume unless ``publish_flags`` allows it)."""

    __tablename__ = "purchase_needs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    spec: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_paid_cents: Mapped[int | None] = mapped_column(BigInteger)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    volume: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    volume_qty: Mapped[int | None] = mapped_column(BigInteger)  # units per month (savings math)
    frequency: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    current_supplier: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    delivery_region: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    deadline: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    restrictions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # reduce_cost | alternative | replace | start
    goal: Mapped[str] = mapped_column(String(12), nullable=False, default="reduce_cost")
    # private | published
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="private")
    publish_flags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

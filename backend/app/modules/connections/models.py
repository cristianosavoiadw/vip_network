from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Connection(IdMixin, TimestampMixin, Base):
    """An approved relationship between two companies (scope §11). One row per pair."""

    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("org_low_id", "org_high_id", name="uq_connections_pair"),)

    org_low_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    org_high_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    requested_by_org_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    # requested | accepted | declined | ended | archived
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="requested")
    # match | manual | event
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

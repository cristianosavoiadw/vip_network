"""A like with an explicit direction and commercial intent (scope §7.2, §23)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

INTENTS = ("buy", "sell", "part", "net")


class Like(IdMixin, TimestampMixin, Base):
    __tablename__ = "likes"
    __table_args__ = (
        # one active like per direction; changing the intent updates the row
        Index(
            "uq_likes_active_pair",
            "source_org_id",
            "target_org_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    source_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    target_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    intent: Mapped[str] = mapped_column(String(4), nullable=False)
    products: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offers.id", ondelete="SET NULL")
    )
    # active | withdrawn | archived
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")

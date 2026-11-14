"""Discovery actions that are not likes (skip, view), saved companies, blocks and reports
(scope §7.4)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class DiscoveryAction(IdMixin, TimestampMixin, Base):
    """skip | view | impression. A skip hides a company for a cool-down period."""

    __tablename__ = "discovery_actions"

    source_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    target_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    sponsored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SavedOrg(IdMixin, TimestampMixin, Base):
    __tablename__ = "saved_orgs"
    __table_args__ = (UniqueConstraint("org_id", "target_org_id", name="uq_saved_orgs"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    target_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )


class OrgBlock(IdMixin, TimestampMixin, Base):
    """A block wins over recommendations, likes, matches and messages, both ways (§23)."""

    __tablename__ = "org_blocks"
    __table_args__ = (UniqueConstraint("source_org_id", "target_org_id", name="uq_org_blocks"),)

    source_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    target_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class Report(IdMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    source_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    target_org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(String(60), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # open | reviewed | dismissed
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="")

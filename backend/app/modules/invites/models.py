"""VIP invitations (owner decision 2026-11-14).

The platform runs in one of three access modes (``settings`` key ``access``): invite only, paid
only, or both. An invited company enters on the VIP plan and gets N invites of its own.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Invite(IdMixin, TimestampMixin, Base):
    __tablename__ = "invites"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    # null inviter org = issued by the VIP Network team (no limit)
    inviter_org_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    inviter_user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    by_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    company_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    # legacy: invites are bound to the e-mail since 2026-11-14 (owner decision); kept empty
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # pending | accepted | expired | revoked
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_org_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

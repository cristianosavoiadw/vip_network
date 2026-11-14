"""E-mail: system templates (one per trigger event), campaigns, sent messages and
suppressions. Same model as BR Licitar's Marketing (owner request 2026-11-14)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class EmailTemplate(IdMixin, TimestampMixin, Base):
    __tablename__ = "email_templates"

    # set on the templates tied to a platform event (mail/triggers.py); editable, never deleted
    system_key: Mapped[str | None] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    preheader: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")  # Markdown + {{ vars }}
    # system | campaign
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="campaign")
    # trigger on/off (mandatory service e-mails ignore it)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class EmailCampaign(IdMixin, TimestampMixin, Base):
    __tablename__ = "email_campaigns"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("email_templates.id", ondelete="SET NULL")
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    preheader: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")  # frozen at start
    # {"segment": "subscribers" | ..., "filters": {...}} — see mail/audiences.py
    audience: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # manual | auto (sequence: steps in `steps`)
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default="manual")
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # draft | scheduled | sending | done | paused | active (auto)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hourly_cap: Mapped[int | None] = mapped_column(Integer)
    recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opened: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unsubscribed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class EmailMessage(IdMixin, TimestampMixin, Base):
    """One e-mail to one address: a trigger (``template_key``) or a campaign message."""

    __tablename__ = "email_messages"
    __table_args__ = (
        Index("ix_email_messages_status", "status"),
        Index("ix_email_messages_campaign", "campaign_id", "status"),
    )

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("email_campaigns.id", ondelete="CASCADE")
    )
    template_key: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    to_email: Mapped[str] = mapped_column(String(254), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # signs the open pixel, click and unsubscribe links of this message
    token: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    # queued | sent | failed | bounced | suppressed
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailSuppression(Base):
    """Addresses that never receive campaigns again (unsubscribed, hard bounce, spam)."""

    __tablename__ = "email_suppressions"

    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

"""Companies (one per CNPJ), their departments, access requests and AI suggestions.

Official data from the CNPJ lookup lives in ``official`` and is never edited by the company;
what the company writes lives in the other columns; what the AI suggests waits in
``ai_suggestions`` until a person approves it (scope §4.1, §4.3).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

SECTORS = ("industria", "logistica", "tecnologia", "servicos", "varejo", "agro", "saude", "outros")


class Organization(IdMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    cnpj: Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    trade_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    # pending (sign-up not finished) | active | suspended (admin)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")

    # official data (CNPJ lookup), read-only for the company
    official: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    official_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cnae_main: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(2), nullable=False, default="")
    size: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    opened_on: Mapped[date | None] = mapped_column(Date)

    # what the company writes (public profile)
    sector: Mapped[str] = mapped_column(String(20), nullable=False, default="outros")
    segment: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_source: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")
    website: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    coverage: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    differentials: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contacts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    certifications: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    logo_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    cover_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#12213F")
    # company presentation (PDF) in the bucket: {key, url, name, size, uploaded_at}; public to
    # members (owner request 2026-11-14)
    presentation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    goals: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # shows in Descobrir and the directory once the onboarding is finished
    discoverable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # onboarding (scope §4.3): last step reached 1..10, finished when completed_at is set
    onboarding_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # how it entered: subscription | invite | staff
    entry: Mapped[str] = mapped_column(String(12), nullable=False, default="subscription")
    invited_by_org_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL")
    )

    @property
    def display_name(self) -> str:
        return self.trade_name or self.legal_name


class Department(IdMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_departments_org_slug"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AccessRequest(IdMixin, TimestampMixin, Base):
    """Someone tried to sign up a CNPJ that already has an account (scope §4.2)."""

    __tablename__ = "access_requests"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    job_title: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    # pending | approved | denied
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiSuggestion(IdMixin, TimestampMixin, Base):
    """A value proposed by an agent for a profile field; applied only after approval."""

    __tablename__ = "ai_suggestions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    field: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # pending | approved | rejected
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="local")

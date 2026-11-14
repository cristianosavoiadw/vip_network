from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

# kind: "admin" (VIP Network team, /admin) or "member" (a company user, /app)
USER_KINDS = ("admin", "member")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # the e-mail is the login (no username); stored lowercase
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="member")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # active | pending (invited, password not created yet) | blocked
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    job_title: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # members only: the company, whether this person owns the account (CEO / Proprietário) and
    # the department slugs (one or more; permissions in organizations/permissions.py)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )
    is_org_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    departments: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # relation with the CNPJ given at sign-up: socio | diretoria | autorizado
    cnpj_relation: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    # admins only: owner | admin | viewer
    admin_role: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    # notification preferences: {"email": {"like.received": false, ...}}
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class RefreshToken(IdMixin, TimestampMixin, Base):
    """One row per session; the cookie holds the raw token, the table only its hash."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip: Mapped[str | None] = mapped_column(String(64))


class AuthToken(IdMixin, TimestampMixin, Base):
    """One-time links by e-mail: verify (confirm the e-mail), activate (invited colleague creates
    the password), reset (forgot the password). Only the hash is stored."""

    __tablename__ = "auth_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(12), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

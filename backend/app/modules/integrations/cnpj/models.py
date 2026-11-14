"""Every CNPJ looked up, kept: a company is not asked again for
30 days, whichever caller asked. ``pending`` = not in our own base, waiting for the public
fallback (rate-limited)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

CNPJ_RECORD_STATUSES = ("found", "not_found", "pending")


class CnpjRecord(Base):
    __tablename__ = "cnpj_records"
    __table_args__ = (Index("ix_cnpj_records_status", "status", "fetched_at"),)

    cnpj: Mapped[str] = mapped_column(String(14), primary_key=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="found")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

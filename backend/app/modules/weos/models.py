"""AI jobs sent to WeOS agents (scope §19.1): status, retries, cost, prompt/model version."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

AGENTS = (
    "CompanyProfileAgent",
    "ProductClassificationAgent",
    "MatchmakingAgent",
    "ProcurementAgent",
    "SalesOpportunityAgent",
    "MarketIntelligenceAgent",
    "NetworkingAgent",
    "MentorshipAgent",
)


class AIJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    agent: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # same key while queued/running = no duplicate execution
    dedupe_key: Mapped[str | None] = mapped_column(String(120), index=True)
    # queued | running | done | failed | dead (dead-letter after max attempts)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_cents: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

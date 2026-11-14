"""/mentorship (company, Diretoria only) and /admin/mentorship (team: agenda only) — §17."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.errors import NotFound
from app.modules.auth.deps import AdminUser, Ctx, DbSession, area
from app.modules.mentorship import service
from app.modules.mentorship.models import Mentor

router = APIRouter(prefix="/mentorship", tags=["mentorship"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

MentorCtx = Annotated[Ctx, Depends(area("mentorship"))]
SESSION_STATUS = "^(requested|scheduled|done|canceled)$"


class SessionIn(BaseModel):
    starts_at: datetime
    topic: str = Field(min_length=2, max_length=160)


class MentorIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    headline: str = Field(default="", max_length=200)
    bio: str = Field(default="", max_length=5000)
    photo_url: str = Field(default="", max_length=300)
    is_lead: bool = False
    active: bool = True


class MentorPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    headline: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=5000)
    photo_url: str | None = Field(default=None, max_length=300)
    is_lead: bool | None = None
    active: bool | None = None


class PlanPatch(BaseModel):
    mentor_id: uuid.UUID | None = None
    sessions_total: int | None = Field(default=None, ge=1, le=200)
    status: str | None = Field(default=None, pattern="^(active|ended|canceled)$")


class ScheduleIn(BaseModel):
    plan_id: uuid.UUID
    starts_at: datetime
    topic: str = Field(min_length=2, max_length=160)


class SessionPatch(BaseModel):
    starts_at: datetime | None = None
    topic: str | None = Field(default=None, min_length=2, max_length=160)
    status: str | None = Field(default=None, pattern=SESSION_STATUS)


# ------------------------------------------------------------------ company


@router.get("")
async def overview(session: DbSession, ctx: MentorCtx) -> dict[str, Any]:
    return await service.overview(session, ctx)


@router.post("/checkout")
async def checkout(session: DbSession, ctx: MentorCtx) -> dict[str, Any]:
    return await service.checkout(session, ctx)


@router.post("/sessions")
async def request_session(body: SessionIn, session: DbSession, ctx: MentorCtx) -> dict[str, Any]:
    s = await service.request_session(session, ctx, body.starts_at, body.topic)
    return service.session_view(s)


# ------------------------------------------------------------------ team panel


@admin_router.get("/mentors")
async def list_mentors(session: DbSession, _: AdminUser) -> dict[str, Any]:
    ms = await service.mentors(session, only_active=False)
    return {"items": [service.mentor_view(m) for m in ms]}


@admin_router.post("/mentors")
async def create_mentor(body: MentorIn, session: DbSession, _: AdminUser) -> dict[str, Any]:
    m = Mentor(**body.model_dump())
    session.add(m)
    await session.flush()
    return service.mentor_view(m)


@admin_router.patch("/mentors/{mentor_id}")
async def update_mentor(
    mentor_id: uuid.UUID, body: MentorPatch, session: DbSession, _: AdminUser
) -> dict[str, Any]:
    m = await session.get(Mentor, mentor_id)
    if m is None:
        raise NotFound("Mentor não encontrado.", code="mentor_not_found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    await session.flush()
    return service.mentor_view(m)


@admin_router.delete("/mentors/{mentor_id}")
async def deactivate_mentor(
    mentor_id: uuid.UUID, session: DbSession, _: AdminUser
) -> dict[str, bool]:
    """Soft delete: the mentor leaves the list; past plans keep the name."""
    m = await session.get(Mentor, mentor_id)
    if m is None:
        raise NotFound("Mentor não encontrado.", code="mentor_not_found")
    m.active = False
    return {"ok": True}


@admin_router.get("/mentorship")
async def admin_overview(session: DbSession, _: AdminUser) -> dict[str, Any]:
    return {
        "summary": await service.admin_summary(session),
        "notice": "A equipe vê só a agenda. Diagnósticos, planos e documentos ficam restritos ao "
        "mentor e à empresa mentorada.",
    }


@admin_router.get("/mentorship/plans")
async def admin_plans(session: DbSession, _: AdminUser) -> dict[str, Any]:
    return {"items": await service.admin_plans(session)}


@admin_router.patch("/mentorship/plans/{plan_id}")
async def admin_update_plan(
    plan_id: uuid.UUID, body: PlanPatch, session: DbSession, _: AdminUser
) -> dict[str, bool]:
    await service.update_plan(session, plan_id, body.model_dump(exclude_unset=True))
    return {"ok": True}


@admin_router.get("/mentorship/agenda")
async def admin_agenda(session: DbSession, _: AdminUser) -> dict[str, Any]:
    return {"items": await service.agenda(session)}


@admin_router.post("/mentorship/sessions")
async def admin_schedule(body: ScheduleIn, session: DbSession, _: AdminUser) -> dict[str, Any]:
    s = await service.schedule(session, body.plan_id, body.starts_at, body.topic)
    return service.session_view(s)


@admin_router.patch("/mentorship/sessions/{session_id}")
async def admin_update_session(
    session_id: uuid.UUID, body: SessionPatch, session: DbSession, _: AdminUser
) -> dict[str, Any]:
    s = await service.update_session(session, session_id, body.model_dump(exclude_unset=True))
    return service.session_view(s)

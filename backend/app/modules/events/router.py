"""/events (company agenda) and /admin/events (team panel) — scope §16."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.modules.auth.deps import AdminUser, Ctx, DbSession, area
from app.modules.events import service

router = APIRouter(prefix="/events", tags=["events"])
admin_router = APIRouter(prefix="/admin/events", tags=["admin"])

EventsCtx = Annotated[Ctx, Depends(area("events"))]
KINDS = "^(jantar|rodada|cafe|encontro)$"
STATUSES = "^(draft|published|canceled)$"


class RatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)


class EventIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    kind: str = Field(default="jantar", pattern=KINDS)
    city: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=2)
    place: str = Field(default="", max_length=200)
    starts_at: datetime
    ends_at: datetime | None = None
    seats: int = Field(default=40, ge=1, le=5000)
    price_cents: int = Field(default=0, ge=0)
    image_url: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=5000)
    status: str = Field(default="published", pattern=STATUSES)


class EventPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    kind: str | None = Field(default=None, pattern=KINDS)
    city: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=2)
    place: str | None = Field(default=None, max_length=200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    seats: int | None = Field(default=None, ge=1, le=5000)
    price_cents: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, pattern=STATUSES)


# ------------------------------------------------------------------ company


@router.get("")
async def list_events(session: DbSession, ctx: EventsCtx) -> dict[str, Any]:
    return {
        "items": await service.list_upcoming(session, ctx),
        "note": "Sugerimos encontros entre empresas com potencial de negócio, sempre com o "
        "consentimento de cada participante. O motivo de uma sugestão nunca expõe compras "
        "privadas.",
    }


@router.post("/{event_id}/register")
async def register(event_id: uuid.UUID, session: DbSession, ctx: EventsCtx) -> dict[str, Any]:
    return await service.register(session, ctx, event_id)


@router.delete("/{event_id}/registration")
async def cancel(event_id: uuid.UUID, session: DbSession, ctx: EventsCtx) -> dict[str, bool]:
    await service.cancel(session, ctx, event_id)
    return {"ok": True}


@router.post("/{event_id}/rating")
async def rate(
    event_id: uuid.UUID, body: RatingIn, session: DbSession, ctx: EventsCtx
) -> dict[str, bool]:
    await service.rate(session, ctx, event_id, body.rating)
    return {"ok": True}


# ------------------------------------------------------------------ team panel


@admin_router.get("")
async def admin_list(session: DbSession, _: AdminUser) -> dict[str, Any]:
    return {"items": await service.admin_list(session)}


@admin_router.post("")
async def admin_create(body: EventIn, session: DbSession, _: AdminUser) -> dict[str, Any]:
    ev = await service.create_event(session, body.model_dump())
    return service.event_view(ev, (await service.event_counts(session, [ev.id]))[ev.id])


@admin_router.post("/checkin/{token}")
async def admin_checkin(token: str, session: DbSession, _: AdminUser) -> dict[str, Any]:
    return await service.checkin(session, token)


@admin_router.patch("/{event_id}")
async def admin_update(
    event_id: uuid.UUID, body: EventPatch, session: DbSession, _: AdminUser
) -> dict[str, Any]:
    ev = await service.update_event(session, event_id, body.model_dump(exclude_unset=True))
    return service.event_view(ev, (await service.event_counts(session, [ev.id]))[ev.id])


@admin_router.get("/{event_id}/registrations")
async def admin_registrations(
    event_id: uuid.UUID, session: DbSession, _: AdminUser
) -> dict[str, Any]:
    return {"items": await service.admin_registrations(session, event_id)}

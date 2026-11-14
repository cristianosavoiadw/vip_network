"""/discovery (cards, actions, saved, blocks, reports, filters), /directory and
/companies/{slug} (company page inside the network)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.discovery import service

router = APIRouter(tags=["discovery"])

DiscoverCtx = Annotated[Ctx, Depends(area("discover"))]


class ActionIn(BaseModel):
    target_org_id: uuid.UUID
    action: Literal["skip", "view", "save", "unsave", "undo_skip"]


class TargetIn(BaseModel):
    target_org_id: uuid.UUID


class ReportIn(BaseModel):
    target_org_id: uuid.UUID
    reason: str = Field(min_length=2, max_length=60)
    details: str = Field(default="", max_length=3000)


@router.get("/discovery/cards")
async def cards(
    session: DbSession,
    ctx: DiscoverCtx,
    sector: str | None = None,
    state: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, Any]]:
    return await service.cards(
        session, ctx, sector=sector or None, state=state or None, limit=limit
    )


@router.post("/discovery/actions")
async def action(body: ActionIn, session: DbSession, ctx: DiscoverCtx) -> dict[str, Any]:
    return await service.act(session, ctx, body.target_org_id, body.action)


@router.get("/discovery/saved")
async def saved(session: DbSession, ctx: DiscoverCtx) -> list[dict[str, Any]]:
    return await service.saved(session, ctx)


@router.get("/discovery/blocks")
async def blocks(session: DbSession, ctx: DiscoverCtx) -> list[dict[str, Any]]:
    return await service.my_blocks(session, ctx)


@router.post("/discovery/blocks")
async def block(body: TargetIn, session: DbSession, ctx: DiscoverCtx) -> dict[str, bool]:
    await service.block(session, ctx, body.target_org_id)
    return {"ok": True}


@router.delete("/discovery/blocks/{target_org_id}")
async def unblock(
    target_org_id: uuid.UUID, session: DbSession, ctx: DiscoverCtx
) -> dict[str, bool]:
    await service.unblock(session, ctx, target_org_id)
    return {"ok": True}


@router.post("/discovery/reports")
async def report(body: ReportIn, session: DbSession, ctx: DiscoverCtx) -> dict[str, Any]:
    row = await service.report(session, ctx, body.target_org_id, body.reason, body.details)
    return {"ok": True, "id": str(row.id)}


@router.get("/discovery/filters")
async def filters(session: DbSession, ctx: DiscoverCtx) -> dict[str, Any]:
    return await service.filters(session, ctx)


@router.get("/directory")
async def directory(
    session: DbSession,
    ctx: DiscoverCtx,
    q: str | None = None,
    sector: str | None = None,
    state: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict[str, Any]:
    return await service.directory(
        session, ctx, q=q, sector=sector or None, state=state or None, page=page
    )


@router.get("/companies/{slug}")
async def company(slug: str, session: DbSession, ctx: DiscoverCtx) -> dict[str, Any]:
    return await service.company_page(session, ctx, slug)

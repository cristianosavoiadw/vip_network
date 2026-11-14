"""/matches: reciprocal matches + AI suggestions, the match modal queue, seen, archive."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.matches import service

router = APIRouter(tags=["matches"])

MatchesCtx = Annotated[Ctx, Depends(area("matches"))]


@router.get("/matches")
async def list_matches(
    session: DbSession, ctx: MatchesCtx, origin: str | None = None, archived: bool = False
) -> list[dict[str, Any]]:
    return await service.list_matches(session, ctx, origin=origin or None, archived=archived)


@router.get("/matches/unseen")
async def unseen(session: DbSession, ctx: MatchesCtx) -> list[dict[str, Any]]:
    return await service.unseen(session, ctx)


@router.get("/matches/{match_id}")
async def get_match(match_id: uuid.UUID, session: DbSession, ctx: MatchesCtx) -> dict[str, Any]:
    return await service.get(session, ctx, match_id)


@router.post("/matches/{match_id}/seen")
async def seen(match_id: uuid.UUID, session: DbSession, ctx: MatchesCtx) -> dict[str, bool]:
    await service.mark_seen(session, ctx, match_id)
    return {"ok": True}


@router.post("/matches/{match_id}/archive")
async def archive(match_id: uuid.UUID, session: DbSession, ctx: MatchesCtx) -> dict[str, bool]:
    await service.archive(session, ctx, match_id)
    return {"ok": True}

"""/intelligence: recommendation cards and market reports (scope §10, §18)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.intelligence import engine, service

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

IntelCtx = Annotated[Ctx, Depends(area("intelligence"))]


@router.get("/recommendations")
async def recommendations(session: DbSession, ctx: IntelCtx) -> dict[str, Any]:
    items = await service.list_recommendations(session, ctx)
    return {
        "items": items,
        "potential_economy_cents": await service.potential_economy_cents(session, ctx.org_id)
        if ctx.can("purchases")
        else None,
        "note": "Valores de economia são estimativas até a confirmação da proposta.",
    }


@router.post("/recommendations/refresh")
async def refresh(session: DbSession, ctx: IntelCtx) -> dict[str, Any]:
    await engine.refresh_for(session, ctx.org_id)
    return {"items": await service.list_recommendations(session, ctx)}


@router.post("/recommendations/{rec_id}/dismiss")
async def dismiss(rec_id: uuid.UUID, session: DbSession, ctx: IntelCtx) -> dict[str, bool]:
    await service.dismiss(session, ctx, rec_id)
    return {"ok": True}


@router.post("/reports")
async def create_report(session: DbSession, ctx: IntelCtx) -> dict[str, Any]:
    rep = await service.create_report(session, ctx)
    return service.report_view(rep)


@router.get("/reports")
async def list_reports(session: DbSession, ctx: IntelCtx) -> dict[str, Any]:
    reps = await service.list_reports(session, ctx.org_id)
    return {"items": [service.report_view(r, full=False) for r in reps]}


@router.get("/reports/{rep_id}")
async def get_report(rep_id: uuid.UUID, session: DbSession, ctx: IntelCtx) -> dict[str, Any]:
    return service.report_view(await service.get_report(session, ctx.org_id, rep_id))

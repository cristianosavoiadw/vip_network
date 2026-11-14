"""/dashboard: Visão Geral (scope §14)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.errors import AppError
from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.dashboard import service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

OverviewCtx = Annotated[Ctx, Depends(area("overview"))]


@router.get("")
async def dashboard(
    session: DbSession, ctx: OverviewCtx, period: Annotated[int, Query()] = 30
) -> dict[str, Any]:
    if period not in service.PERIODS:
        raise AppError("Período inválido. Use 7, 30 ou 90 dias.", code="invalid_period")
    return await service.dashboard(session, ctx, period)

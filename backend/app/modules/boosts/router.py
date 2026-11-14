"""/boosts (Brilhar na Rede) and /admin/boosts — scope §2.2.

Buying needs the "sales" area; reading (packages, campaigns, analytics) is open to "sales"
and "billing" (the Brilhar block of Assinatura)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.errors import Forbidden
from app.modules.auth.deps import ActiveCtx, AdminUser, Ctx, DbSession, area
from app.modules.boosts import service

router = APIRouter(prefix="/boosts", tags=["boosts"])
admin_router = APIRouter(prefix="/admin/boosts", tags=["admin"])

BuyCtx = Annotated[Ctx, Depends(area("sales"))]


async def _reader(ctx: ActiveCtx) -> Ctx:
    if not (ctx.can("sales") or ctx.can("billing")):
        raise Forbidden(
            "Seu departamento não tem acesso a esta área. Peça à Diretoria.", code="no_access"
        )
    return ctx


ReadCtx = Annotated[Ctx, Depends(_reader)]


class CheckoutIn(BaseModel):
    days: int


@router.get("/packages")
async def packages(_: ReadCtx) -> dict[str, Any]:
    return {"items": service.packages(), "disclaimer": service.DISCLAIMER}


@router.post("/checkout")
async def checkout(body: CheckoutIn, session: DbSession, ctx: BuyCtx) -> dict[str, Any]:
    return await service.checkout(session, ctx, body.days)


@router.get("/campaigns")
async def campaigns(session: DbSession, ctx: ReadCtx) -> dict[str, Any]:
    return {"items": await service.campaigns(session, ctx.org_id)}


@router.get("/analytics")
async def analytics(session: DbSession, ctx: ReadCtx) -> dict[str, Any]:
    return await service.analytics(session, ctx.org_id)


@admin_router.get("")
async def admin_overview(session: DbSession, _: AdminUser) -> dict[str, Any]:
    return await service.admin_overview(session)

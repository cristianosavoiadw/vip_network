"""/likes: like with intent, withdraw, archive, Minhas Curtidas lists and badge counts."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.likes import service

router = APIRouter(tags=["likes"])

LikesCtx = Annotated[Ctx, Depends(area("likes"))]
Tab = Literal["compras", "vendas", "parcerias", "todos"]
Filter = Literal["all", "sent", "received", "mutual", "waiting", "matched", "archived"]


class LikeIn(BaseModel):
    target_org_id: uuid.UUID
    intent: Literal["buy", "sell", "part", "net"]
    products: list[str] = Field(default_factory=list, max_length=10)
    offer_id: uuid.UUID | None = None


@router.post("/likes")
async def like(body: LikeIn, session: DbSession, ctx: LikesCtx) -> dict[str, Any]:
    return await service.like(
        session,
        ctx,
        target_org_id=body.target_org_id,
        intent=body.intent,
        products=body.products,
        offer_id=body.offer_id,
    )


@router.get("/likes")
async def list_likes(
    session: DbSession,
    ctx: LikesCtx,
    tab: Tab = "todos",
    filter_: Annotated[Filter, Query(alias="filter")] = "all",
) -> dict[str, Any]:
    return await service.grouped(session, ctx, tab=tab, f=filter_)


@router.get("/likes/summary")
async def summary(session: DbSession, ctx: LikesCtx) -> dict[str, Any]:
    return await service.summary(session, ctx)


@router.delete("/likes/{like_id}")
async def withdraw(like_id: uuid.UUID, session: DbSession, ctx: LikesCtx) -> dict[str, Any]:
    lk = await service.withdraw(session, ctx, like_id)
    return {
        "ok": True,
        "like": service.like_view(lk),
        "message": "Curtida retirada. Ela deixa de gerar novos matches.",
    }


@router.post("/likes/{like_id}/archive")
async def archive(like_id: uuid.UUID, session: DbSession, ctx: LikesCtx) -> dict[str, bool]:
    await service.archive(session, ctx, like_id)
    return {"ok": True}

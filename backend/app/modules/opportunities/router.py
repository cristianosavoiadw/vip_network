"""/opportunities: the company's commercial funnel (Oportunidades) (scope §12, §15)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.opportunities import service
from app.modules.organizations.views import iso

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

OppCtx = Annotated[Ctx, Depends(area("opportunities"))]
Stage = Literal["new", "contact", "qualification", "negotiation", "proposal", "won", "lost"]


class OpportunityIn(BaseModel):
    target_org_id: uuid.UUID
    kind: Literal["buy", "sell", "part"]
    title: str = Field(min_length=2, max_length=200)
    product: str = Field(default="", max_length=300)
    value_estimate_cents: int | None = Field(default=None, ge=0)
    next_action: str = Field(default="", max_length=200)


class OpportunityPatch(BaseModel):
    stage: Stage | None = None
    next_action: str | None = Field(default=None, max_length=200)
    value_estimate_cents: int | None = Field(default=None, ge=0)
    owner_user_id: uuid.UUID | None = None


class NoteIn(BaseModel):
    body: str = Field(default="", max_length=5000)


class CloseIn(BaseModel):
    won: bool
    value_cents: int | None = Field(default=None, ge=0)


@router.get("")
async def list_opportunities(
    ctx: OppCtx,
    session: DbSession,
    kind: Annotated[Literal["buy", "sell", "part"] | None, Query()] = None,
    stage: Annotated[Stage | None, Query()] = None,
) -> dict[str, Any]:
    opps = await service.list_for(session, ctx.org_id, kind=kind, stage=stage)
    items = await service.rows_view(session, opps, ctx.org_id)
    return {
        "items": items,
        "stages": [{"key": k, "label": v} for k, v in service.STAGE_LABELS.items()],
    }


@router.post("")
async def create_opportunity(
    body: OpportunityIn, ctx: OppCtx, session: DbSession
) -> dict[str, Any]:
    opp = await service.create(
        session,
        org_id=ctx.org_id,
        user=ctx.user,
        target_org_id=body.target_org_id,
        kind=body.kind,
        title=body.title,
        product=body.product,
        value_estimate_cents=body.value_estimate_cents,
        next_action=body.next_action,
    )
    return await service.detail_view(session, opp, ctx.org_id)


@router.post("/from-match/{match_id}")
async def from_match(match_id: str, ctx: OppCtx, session: DbSession) -> dict[str, Any]:
    opp, conv_id, created = await service.from_match(
        session, org_id=ctx.org_id, user=ctx.user, match_id=match_id
    )
    return {
        "opportunity": await service.detail_view(session, opp, ctx.org_id),
        "conversation_id": str(conv_id),
        "created": created,
    }


@router.get("/{opp_id}")
async def get_opportunity(opp_id: str, ctx: OppCtx, session: DbSession) -> dict[str, Any]:
    opp = await service.get_for(session, ctx.org_id, opp_id)
    return await service.detail_view(session, opp, ctx.org_id)


@router.patch("/{opp_id}")
async def patch_opportunity(
    opp_id: str, body: OpportunityPatch, ctx: OppCtx, session: DbSession
) -> dict[str, Any]:
    opp = await service.get_for(session, ctx.org_id, opp_id)
    await service.update(
        session, opp, org_id=ctx.org_id, user=ctx.user, fields=body.model_dump(exclude_unset=True)
    )
    return await service.detail_view(session, opp, ctx.org_id)


@router.put("/{opp_id}/note")
async def put_note(opp_id: str, body: NoteIn, ctx: OppCtx, session: DbSession) -> dict[str, Any]:
    opp = await service.get_for(session, ctx.org_id, opp_id)
    note = await service.put_note(session, opp, org_id=ctx.org_id, body=body.body)
    return {"body": note.body, "updated_at": iso(note.updated_at)}


@router.post("/{opp_id}/close")
async def close_opportunity(
    opp_id: str, body: CloseIn, ctx: OppCtx, session: DbSession
) -> dict[str, Any]:
    opp = await service.get_for(session, ctx.org_id, opp_id)
    await service.close(
        session, opp, org_id=ctx.org_id, user=ctx.user, won=body.won, value_cents=body.value_cents
    )
    return await service.detail_view(session, opp, ctx.org_id)

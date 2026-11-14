"""/conversations (Mensagens) and /uploads (chat attachments) (scope §12)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.messaging import service, uploads
from app.modules.organizations.views import iso

router = APIRouter(tags=["messaging"])
router.include_router(uploads.router)

MsgCtx = Annotated[Ctx, Depends(area("messages"))]


class ConversationIn(BaseModel):
    target_org_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    title: str = Field(default="", max_length=200)


class MessageIn(BaseModel):
    kind: Literal["text", "proposal_request", "meeting", "decision", "attachment", "product"] = (
        "text"
    )
    body: str = Field(default="", max_length=5000)
    data: dict[str, Any] = Field(default_factory=dict)


class ParticipantsIn(BaseModel):
    departments: list[str] = Field(default_factory=list, max_length=20)


@router.get("/conversations")
async def list_conversations(ctx: MsgCtx, session: DbSession) -> dict[str, Any]:
    items = await service.list_for(session, ctx.user)
    return {"items": items, "unread": sum(i["unread"] for i in items)}


@router.post("/conversations")
async def start_conversation(
    body: ConversationIn, ctx: MsgCtx, session: DbSession
) -> dict[str, Any]:
    conv, created = await service.start(
        session,
        user=ctx.user,
        org_id=ctx.org_id,
        target_org_id=body.target_org_id,
        opportunity_id=body.opportunity_id,
        title=body.title,
    )
    return {**await service.detail(session, conv, ctx.user), "created": created}


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, ctx: MsgCtx, session: DbSession) -> dict[str, Any]:
    conv = await service.get_for(session, ctx.user, conv_id)
    return await service.detail(session, conv, ctx.user)


@router.put("/conversations/{conv_id}/participants")
async def set_participants(
    conv_id: str, body: ParticipantsIn, ctx: MsgCtx, session: DbSession
) -> dict[str, Any]:
    conv = await service.get_for(session, ctx.user, conv_id)
    await service.set_departments(session, conv, org_id=ctx.org_id, departments=body.departments)
    return {"participants": await service.participants(session, conv, ctx.org_id)}


@router.get("/conversations/{conv_id}/messages")
async def list_messages(
    conv_id: str,
    ctx: MsgCtx,
    session: DbSession,
    before: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    conv = await service.get_for(session, ctx.user, conv_id)
    rows, has_more = await service.page(session, conv, before=before, limit=limit)
    return {
        "items": await service.messages_view(session, rows, ctx.org_id),
        "has_more": has_more,
    }


@router.post("/conversations/{conv_id}/messages")
async def send_message(
    conv_id: str, body: MessageIn, ctx: MsgCtx, session: DbSession
) -> dict[str, Any]:
    conv = await service.get_for(session, ctx.user, conv_id)
    msg = await service.send(
        session, conv, ctx.user, kind=body.kind, body=body.body, data=body.data
    )
    return (await service.messages_view(session, [msg], ctx.org_id))[0]


@router.post("/conversations/{conv_id}/read")
async def read_conversation(conv_id: str, ctx: MsgCtx, session: DbSession) -> dict[str, Any]:
    conv = await service.get_for(session, ctx.user, conv_id)
    at = await service.mark_read(session, conv, ctx.user)
    return {"ok": True, "last_read_at": iso(at)}

"""/connections (request, accept, decline, end, archive) and /network (Minha Rede)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.connections import service
from app.modules.connections.models import Connection
from app.modules.organizations.models import Organization

router = APIRouter(tags=["connections"])

NetworkCtx = Annotated[Ctx, Depends(area("network"))]


class RequestIn(BaseModel):
    target_org_id: uuid.UUID
    message: str = Field(default="", max_length=1000)


async def _view(session: DbSession, ctx: Ctx, c: Connection) -> dict[str, Any]:
    other = await session.get(Organization, service.other_of(c, ctx.org_id))
    assert other is not None
    return service.connection_view(c, ctx.org_id, other)


@router.get("/connections")
async def list_connections(
    session: DbSession,
    ctx: NetworkCtx,
    status: Literal["requested", "accepted", "declined", "ended", "archived"] | None = None,
) -> list[dict[str, Any]]:
    return await service.list_connections(session, ctx, status=status)


@router.post("/connections/request")
async def request(body: RequestIn, session: DbSession, ctx: NetworkCtx) -> dict[str, Any]:
    c = await service.request(session, ctx, body.target_org_id, body.message)
    return await _view(session, ctx, c)


@router.post("/connections/{connection_id}/accept")
async def accept(connection_id: uuid.UUID, session: DbSession, ctx: NetworkCtx) -> dict[str, Any]:
    return await _view(session, ctx, await service.accept(session, ctx, connection_id))


@router.post("/connections/{connection_id}/decline")
async def decline(connection_id: uuid.UUID, session: DbSession, ctx: NetworkCtx) -> dict[str, Any]:
    return await _view(session, ctx, await service.decline(session, ctx, connection_id))


@router.post("/connections/{connection_id}/end")
async def end(connection_id: uuid.UUID, session: DbSession, ctx: NetworkCtx) -> dict[str, Any]:
    return await _view(session, ctx, await service.end(session, ctx, connection_id))


@router.post("/connections/{connection_id}/archive")
async def archive(connection_id: uuid.UUID, session: DbSession, ctx: NetworkCtx) -> dict[str, Any]:
    return await _view(session, ctx, await service.archive(session, ctx, connection_id))


@router.get("/network")
async def network(session: DbSession, ctx: NetworkCtx) -> dict[str, Any]:
    return await service.network(session, ctx)

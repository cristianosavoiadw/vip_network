"""/notifications (bell) and the authenticated WebSocket (/ws?token=<access token>)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core import realtime
from app.core.security import decode_access_token
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.notifications import service
from app.modules.notifications.models import Notification
from app.modules.organizations.views import iso

router = APIRouter(tags=["notifications"])


class ReadIn(BaseModel):
    ids: list[uuid.UUID] | None = None


@router.get("/notifications")
async def list_notifications(user: CurrentUser, session: DbSession) -> dict[str, Any]:
    rows = await service.list_for(session, user.id)
    unread = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user.id, Notification.read_at.is_(None))
            )
        ).scalar_one()
    )
    return {
        "unread": unread,
        "items": [
            {
                "id": str(n.id),
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "link": n.link,
                "read": n.read_at is not None,
                "created_at": iso(n.created_at),
            }
            for n in rows
        ],
    }


@router.post("/notifications/read")
async def read(body: ReadIn, user: CurrentUser, session: DbSession) -> dict[str, bool]:
    await service.mark_read(session, user.id, body.ids)
    return {"ok": True}


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=4401)
        return
    user_id = uuid.UUID(payload["sub"])
    await websocket.accept()
    queue = realtime.subscribe(user_id)
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=25)
            except TimeoutError:
                msg = {"type": "ping"}
            await websocket.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        realtime.unsubscribe(user_id, queue)

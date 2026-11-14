"""Public e-mail endpoints: open pixel, unsubscribe. The team panel (templates, triggers,
campaigns, messages, settings) is in ``mail/admin.py``, mounted here as ``admin_router``."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from app.modules.auth.deps import DbSession
from app.modules.mail import service
from app.modules.mail.models import EmailMessage

public_router = APIRouter(prefix="/mail", tags=["mail"])

PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


async def _by_token(session: DbSession, token: str) -> EmailMessage | None:
    return (
        await session.execute(select(EmailMessage).where(EmailMessage.token == token))
    ).scalar_one_or_none()


@public_router.get("/o/{token}.gif", include_in_schema=False)
async def opened(token: str, session: DbSession) -> Response:
    msg = await _by_token(session, token)
    if msg is not None and msg.opened_at is None:
        msg.opened_at = datetime.now(UTC)
    return Response(PIXEL, media_type="image/gif", headers={"Cache-Control": "no-store"})


@public_router.get("/unsubscribe/{token}", include_in_schema=False)
async def unsubscribe(token: str, session: DbSession) -> HTMLResponse:
    msg = await _by_token(session, token)
    if msg is not None:
        msg.unsubscribed_at = msg.unsubscribed_at or datetime.now(UTC)
        await service.suppress(session, msg.to_email, "unsubscribed")
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><title>VIP Network</title>"
        "<body style='font-family:Arial;padding:40px;color:#0E1930'>"
        "<h2>Descadastro confirmado</h2><p>Você não vai mais receber campanhas da VIP Network. "
        "E-mails sobre a sua conta continuam chegando.</p></body>"
    )


try:  # the team panel lives in its own file
    from app.modules.mail.admin import router as admin_router  # noqa: F401
except ModuleNotFoundError:
    pass

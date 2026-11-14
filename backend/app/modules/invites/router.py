"""/invites: public validation of a code, the company's own invites (Indicar Empresas) and the
team panel (Admin › Acesso e convites)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.modules.auth.deps import AdminUser, Ctx, DbSession, area
from app.modules.invites import importer, service
from app.modules.invites.models import Invite
from app.modules.organizations.views import iso
from app.modules.settings import service as settings_service

public_router = APIRouter(prefix="/invites", tags=["invites"])
router = APIRouter(prefix="/invites", tags=["invites"])
admin_router = APIRouter(prefix="/admin/access", tags=["admin"])

InvitesCtx = Annotated[Ctx, Depends(area("invites"))]


class InviteIn(BaseModel):
    """No CNPJ: the e-mail identifies the invite (owner decision 2026-11-14)."""

    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)
    email: str
    company_name: str = Field(min_length=2, max_length=160)
    message: str = Field(default="", max_length=600)


class AccessIn(BaseModel):
    mode: str | None = None
    vip_months: int | None = None
    invites_per_member: int | None = None
    who_invites: str | None = None
    invite_ttl_days: int | None = None
    bind_email: bool | None = None
    return_expired: bool | None = None
    vip_reminders: bool | None = None


def _view(inv: Invite) -> dict[str, Any]:
    return {
        "id": str(inv.id),
        "code": inv.code,
        "first_name": inv.first_name,
        "last_name": inv.last_name,
        "company_name": inv.company_name,
        "email": inv.email,
        "status": inv.status,
        "created_at": iso(inv.created_at),
        "expires_at": iso(inv.expires_at),
        "accepted_at": iso(inv.accepted_at),
        "link": service.invite_link(inv.code),
    }


@public_router.get("/access")
async def access_mode(session: DbSession) -> dict[str, Any]:
    """What the public site needs to show the right buttons."""
    conf = await settings_service.get(session, "access")
    return {
        "mode": conf["mode"],
        "vip_months": settings_service.vip_months(conf),
        "invites_per_member": conf["invites_per_member"],
    }


@public_router.get("/check/{code}")
async def check(code: str, session: DbSession) -> dict[str, Any]:
    inv = await service.validate(session, code)
    return await service.public_view(session, inv)


@router.get("")
async def mine(ctx: InvitesCtx, session: DbSession) -> dict[str, Any]:
    data = await service.summary(session, ctx.org)
    return {
        **{k: v for k, v in data.items() if k != "invites"},
        "invites": [_view(i) for i in data["invites"]],
    }


@router.post("")
async def send(body: InviteIn, ctx: InvitesCtx, session: DbSession) -> dict[str, Any]:
    inv = await service.create(
        session,
        org=ctx.org,
        user=ctx.user,
        first_name=body.first_name,
        last_name=body.last_name,
        company_name=body.company_name,
        email=body.email,
        message=body.message,
    )
    return _view(inv)


@router.post("/{invite_id}/revoke")
async def revoke(invite_id: uuid.UUID, ctx: InvitesCtx, session: DbSession) -> dict[str, Any]:
    return _view(
        await service.revoke(session, await service.get_own(session, ctx.org_id, invite_id))
    )


@router.post("/{invite_id}/resend")
async def resend(invite_id: uuid.UUID, ctx: InvitesCtx, session: DbSession) -> dict[str, Any]:
    inv = await service.get_own(session, ctx.org_id, invite_id)
    return _view(await service.resend(session, inv, ctx.org.display_name))


# ------------------------------------------------------------------ team panel


@admin_router.get("")
async def get_access(admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await settings_service.get(session, "access")


@admin_router.patch("")
async def put_access(body: AccessIn, admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await settings_service.put(
        session, "access", body.model_dump(exclude_none=True), user_id=admin.id
    )


@admin_router.get("/invites")
async def all_invites(
    admin: AdminUser, session: DbSession, status: str | None = None
) -> list[dict[str, Any]]:
    return await service.staff_list(session, status=status)


@admin_router.post("/invites")
async def staff_invite(body: InviteIn, admin: AdminUser, session: DbSession) -> dict[str, Any]:
    inv = await service.create(
        session,
        org=None,
        user=admin,
        first_name=body.first_name,
        last_name=body.last_name,
        company_name=body.company_name,
        email=body.email,
        message=body.message,
        by_staff=True,
    )
    return _view(inv)


@admin_router.get("/invites/template")
async def import_template(admin: AdminUser) -> Response:
    """The Excel layout to fill (Nome, Sobrenome, E-mail, Empresa, Mensagem)."""
    return Response(
        importer.template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="convites-vip-network.xlsx"'},
    )


@admin_router.post("/invites/import")
async def import_invites(
    admin: AdminUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
    send: bool = False,
) -> dict[str, Any]:
    """``send=false``: check the rows and show the preview. ``send=true``: send the valid ones."""
    data = await file.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise AppError("A planilha pode ter no máximo 5 MB.", code="file_too_large")
    return await importer.run(session, data, user=admin, send=send)


@admin_router.get("/tree")
async def invite_tree(admin: AdminUser, session: DbSession) -> list[dict[str, Any]]:
    return await service.tree(session)

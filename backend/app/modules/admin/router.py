"""/admin: team panel (Visão geral, Assinaturas, Rede, Matchmaking, Suporte e moderação, equipe).

Every route takes ``AdminUser``: a ``viewer`` only reads (enforced by the dependency).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.modules.admin import service
from app.modules.auth.deps import AdminUser, DbSession, client_ip

router = APIRouter(prefix="/admin", tags=["admin"])


class VerifyIn(BaseModel):
    verified: bool = True


class ReportIn(BaseModel):
    status: str
    resolution: str = Field(default="", max_length=2000)


class StaffIn(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=120)
    admin_role: str = "admin"


class StaffPatch(BaseModel):
    admin_role: str | None = None
    blocked: bool | None = None


@router.get("/overview")
async def overview(admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await service.overview(session)


@router.get("/subscriptions")
async def subscriptions(
    admin: AdminUser,
    session: DbSession,
    status: str | None = None,
    kind: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    return await service.subscriptions(session, status=status, kind=kind, q=q)


@router.get("/orgs")
async def orgs(
    admin: AdminUser,
    session: DbSession,
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
) -> dict[str, Any]:
    return await service.orgs(session, q=q, status=status, page=page)


@router.get("/orgs/{org_id}")
async def org_detail(org_id: uuid.UUID, admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await service.org_detail(session, org_id)


@router.post("/orgs/{org_id}/suspend")
async def suspend(
    org_id: uuid.UUID, request: Request, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    return await service.set_org_state(session, org_id, "suspend", admin, ip=client_ip(request))


@router.post("/orgs/{org_id}/reactivate")
async def reactivate(
    org_id: uuid.UUID, request: Request, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    return await service.set_org_state(session, org_id, "reactivate", admin, ip=client_ip(request))


@router.post("/orgs/{org_id}/verify")
async def verify(
    org_id: uuid.UUID,
    request: Request,
    admin: AdminUser,
    session: DbSession,
    body: VerifyIn | None = None,
) -> dict[str, Any]:
    return await service.set_org_state(
        session,
        org_id,
        "verify",
        admin,
        ip=client_ip(request),
        verified=body.verified if body else True,
    )


@router.get("/matchmaking")
async def matchmaking(admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await service.matchmaking(session)


@router.get("/support")
async def support(admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await service.support(session)


@router.post("/support/reports/{report_id}")
async def review_report(
    report_id: uuid.UUID, body: ReportIn, request: Request, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    return await service.review_report(
        session,
        report_id,
        status=body.status,
        resolution=body.resolution,
        admin=admin,
        ip=client_ip(request),
    )


@router.post("/support/access-requests/{req_id}/remind")
async def remind_access_request(
    req_id: uuid.UUID, request: Request, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    return await service.remind_access_request(session, req_id, admin=admin, ip=client_ip(request))


@router.get("/team")
async def team(admin: AdminUser, session: DbSession) -> list[dict[str, Any]]:
    return await service.team(session)


@router.post("/team")
async def invite_staff(body: StaffIn, admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await service.invite_staff(
        session, email=body.email, full_name=body.full_name, admin_role=body.admin_role, by=admin
    )


@router.patch("/team/{user_id}")
async def update_staff(
    user_id: uuid.UUID, body: StaffPatch, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    return await service.update_staff(
        session, user_id, admin_role=body.admin_role, blocked=body.blocked, by=admin
    )

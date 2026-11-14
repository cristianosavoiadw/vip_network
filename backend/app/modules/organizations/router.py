"""/organizations (CNPJ lookup, access requests, own profile, onboarding, AI suggestions) and
/team (people and departments)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.modules.auth.deps import Ctx, DbSession, MemberCtx, area, area_any_status
from app.modules.organizations import service
from app.modules.organizations.models import AccessRequest, AiSuggestion, Organization
from app.modules.organizations.views import iso, org_private, org_public, user_view

public_router = APIRouter(prefix="/organizations", tags=["organizations"])
router = APIRouter(tags=["organizations"])

CompanyCtx = Annotated[Ctx, Depends(area_any_status("company"))]
TeamCtx = Annotated[Ctx, Depends(area_any_status("team"))]


class AccessRequestIn(BaseModel):
    cnpj: str
    full_name: str = Field(min_length=3, max_length=120)
    email: str
    job_title: str = Field(default="", max_length=80)


class ProfileIn(BaseModel):
    trade_name: str | None = Field(default=None, max_length=160)
    sector: str | None = None
    segment: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=3000)
    website: str | None = Field(default=None, max_length=200)
    coverage: str | None = Field(default=None, max_length=120)
    differentials: str | None = Field(default=None, max_length=2000)
    contacts: list[dict[str, Any]] | None = None
    certifications: list[dict[str, Any]] | None = None
    logo_url: str | None = Field(default=None, max_length=300)
    cover_url: str | None = Field(default=None, max_length=300)
    goals: list[str] | None = None


class StepIn(BaseModel):
    step: int


class DecideIn(BaseModel):
    approve: bool
    value: str | None = None
    departments: list[str] = []


class MemberIn(BaseModel):
    email: str
    full_name: str = Field(default="", max_length=120)
    departments: list[str]


class MemberPatch(BaseModel):
    departments: list[str] | None = None
    blocked: bool | None = None


class DepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


# ------------------------------------------------------------------ public


@public_router.get("/cnpj/{cnpj}/lookup")
async def lookup(cnpj: str, session: DbSession) -> dict[str, Any]:
    return await service.lookup(session, cnpj)


@public_router.post("/access-requests")
async def access_request(body: AccessRequestIn, session: DbSession) -> dict[str, bool]:
    await service.request_access(
        session,
        cnpj=body.cnpj,
        full_name=body.full_name,
        email=body.email,
        job_title=body.job_title,
    )
    return {"ok": True}


@public_router.get("/by-slug/{slug}")
async def public_profile(
    slug: str, session: DbSession, ctx: Annotated[Ctx, Depends(area("discover"))]
) -> dict[str, Any]:
    """A company's public page inside the network (offers come from /catalog)."""
    from app.core.errors import NotFound

    org = (
        await session.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if org is None or org.status != "active":
        raise NotFound("Empresa não encontrada.")
    return org_public(org)


# ------------------------------------------------------------------ own company


@router.get("/organizations/me")
async def my_org(ctx: MemberCtx) -> dict[str, Any]:
    return org_private(ctx.org)


@router.patch("/organizations/me")
async def update_my_org(body: ProfileIn, ctx: CompanyCtx) -> dict[str, Any]:
    await service.update_profile(None, ctx.org, body.model_dump(exclude_none=True))  # type: ignore[arg-type]
    return org_private(ctx.org)


@router.post("/organizations/me/onboarding/step")
async def onboarding_step(body: StepIn, ctx: MemberCtx) -> dict[str, Any]:
    await service.set_step(ctx.org, body.step)
    return {"onboarding_step": ctx.org.onboarding_step}


@router.post("/organizations/me/onboarding/complete")
async def onboarding_complete(ctx: MemberCtx, session: DbSession) -> dict[str, Any]:
    await service.complete_onboarding(session, ctx.org, ctx.user)
    return org_private(ctx.org)


@router.get("/organizations/me/suggestions")
async def suggestions(ctx: CompanyCtx, session: DbSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(AiSuggestion)
            .where(AiSuggestion.org_id == ctx.org_id, AiSuggestion.status == "pending")
            .order_by(AiSuggestion.created_at.desc())
        )
    ).scalars()
    return [{"id": str(s.id), "field": s.field, "value": s.value, "source": s.source} for s in rows]


@router.post("/organizations/me/suggestions/description")
async def suggest_description(ctx: CompanyCtx, session: DbSession) -> dict[str, Any]:
    sug = await service.create_description_suggestion(session, ctx.org)
    return {"id": str(sug.id), "field": sug.field, "value": sug.value, "source": sug.source}


@router.post("/organizations/me/suggestions/{sug_id}")
async def decide_suggestion(
    sug_id: uuid.UUID, body: DecideIn, ctx: CompanyCtx, session: DbSession
) -> dict[str, Any]:
    await service.decide_suggestion(
        session, ctx.org, sug_id, approve=body.approve, value=body.value
    )
    return org_private(ctx.org)


# ------------------------------------------------------------------ team


@router.get("/team")
async def list_team(ctx: TeamCtx, session: DbSession) -> dict[str, Any]:
    people = await service.team(session, ctx.org_id)
    depts = await service.departments(session, ctx.org_id)
    requests = (
        await session.execute(
            select(AccessRequest).where(
                AccessRequest.org_id == ctx.org_id, AccessRequest.status == "pending"
            )
        )
    ).scalars()
    return {
        "members": [user_view(u) for u in people],
        "departments": [
            {"id": str(d.id), "slug": d.slug, "name": d.name, "builtin": d.builtin} for d in depts
        ],
        "access_requests": [
            {
                "id": str(r.id),
                "email": r.email,
                "full_name": r.full_name,
                "job_title": r.job_title,
                "created_at": iso(r.created_at),
            }
            for r in requests
        ],
    }


@router.post("/team/members")
async def add_member(body: MemberIn, ctx: TeamCtx, session: DbSession) -> dict[str, Any]:
    user = await service.invite_member(
        session,
        ctx.org,
        ctx.user,
        email=body.email,
        full_name=body.full_name,
        departments=body.departments,
    )
    return user_view(user)


@router.patch("/team/members/{user_id}")
async def patch_member(
    user_id: uuid.UUID, body: MemberPatch, ctx: TeamCtx, session: DbSession
) -> dict[str, Any]:
    user = await service.update_member(
        session,
        ctx.org,
        user_id,
        departments=body.departments,
        blocked=body.blocked,
        actor=ctx.user,
    )
    return user_view(user)


@router.delete("/team/members/{user_id}")
async def delete_member(user_id: uuid.UUID, ctx: TeamCtx, session: DbSession) -> dict[str, bool]:
    await service.remove_member(session, ctx.org, user_id, ctx.user)
    return {"ok": True}


@router.post("/team/departments")
async def add_department(body: DepartmentIn, ctx: TeamCtx, session: DbSession) -> dict[str, Any]:
    d = await service.add_department(session, ctx.org, body.name)
    return {"id": str(d.id), "slug": d.slug, "name": d.name, "builtin": d.builtin}


@router.delete("/team/departments/{dept_id}")
async def delete_department(
    dept_id: uuid.UUID, ctx: TeamCtx, session: DbSession
) -> dict[str, bool]:
    await service.delete_department(session, ctx.org, dept_id)
    return {"ok": True}


@router.post("/team/access-requests/{req_id}")
async def decide_access(
    req_id: uuid.UUID, body: DecideIn, ctx: TeamCtx, session: DbSession
) -> dict[str, bool]:
    await service.decide_access(
        session,
        ctx.org,
        req_id,
        approve=body.approve,
        departments=body.departments,
        decided_by=ctx.user,
    )
    return {"ok": True}

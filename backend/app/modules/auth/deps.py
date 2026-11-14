"""Who is calling and what they may reach.

Company routes take a ``Ctx`` (user + organization) from ``area("<name>")``: it checks the
session, the company status, the subscription and the department permission, in that order.
Every query of company data must use ``ctx.org_id`` — never an organization id sent by the
frontend (scope §22).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_session
from app.modules.auth.models import User
from app.modules.billing.entitlement import entitled
from app.modules.billing.models import Subscription
from app.modules.organizations import permissions
from app.modules.organizations.models import Organization

_bearer = HTTPBearer(auto_error=False)
# scope="function": the commit happens before the response is sent, so the next request of the
# same client always sees what this one wrote.
DbSession = Annotated[AsyncSession, Depends(get_session, scope="function")]


class PaymentRequired(AppError):
    status_code = 402
    code = "subscription_required"


async def get_current_user(
    session: DbSession, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    if creds is None:
        raise Unauthorized("Entre para continuar.", code="missing_token")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Sua sessão expirou.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Sessão inválida.", code="token_invalid") from exc
    user = await session.get(User, uuid.UUID(payload["sub"]))
    if user is None or user.status != "active":
        raise Unauthorized("Este acesso está bloqueado.", code="user_blocked")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class Ctx:
    user: User
    org: Organization
    subscription: Subscription | None = None
    areas: list[str] = field(default_factory=list)

    @property
    def org_id(self) -> uuid.UUID:
        return self.org.id

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def is_owner(self) -> bool:
        return self.user.is_org_owner

    def can(self, area: str) -> bool:
        return area in self.areas

    def sees_intent(self, intent: str) -> bool:
        return permissions.sees_intent(
            self.user.departments, intent, is_owner=self.user.is_org_owner
        )


async def member_ctx(session: DbSession, user: CurrentUser) -> Ctx:
    """A company user of a company that is not suspended (sign-up may be unfinished)."""
    if user.kind != "member" or user.org_id is None:
        raise Forbidden("Área das empresas. Entre com a conta da sua empresa.", code="wrong_area")
    org = await session.get(Organization, user.org_id)
    if org is None or org.status == "suspended":
        raise Forbidden(
            "A conta da sua empresa está suspensa. Fale com a VIP Network.",
            code="org_suspended",
        )
    sub = (
        await session.execute(select(Subscription).where(Subscription.org_id == org.id))
    ).scalar_one_or_none()
    areas = permissions.areas_for(user.departments, is_owner=user.is_org_owner)
    return Ctx(user=user, org=org, subscription=sub, areas=areas)


MemberCtx = Annotated[Ctx, Depends(member_ctx)]


async def active_ctx(ctx: MemberCtx) -> Ctx:
    """Sign-up finished and a valid subscription (trial, paid or VIP)."""
    if ctx.org.status != "active":
        raise Forbidden("Termine o cadastro da empresa para continuar.", code="onboarding")
    if not entitled(ctx.subscription):
        raise PaymentRequired(
            "A assinatura da sua empresa não está ativa. Veja em Assinatura e Pagamentos.",
        )
    return ctx


ActiveCtx = Annotated[Ctx, Depends(active_ctx)]


def area(name: str) -> Callable[..., Awaitable[Ctx]]:
    """Dependency: active company + the user's departments reach ``name``."""
    if name not in permissions.AREAS:
        raise ValueError(f"unknown area {name}")

    async def dep(ctx: ActiveCtx) -> Ctx:
        if not ctx.can(name):
            raise Forbidden(
                "Seu departamento não tem acesso a esta área. Peça à Diretoria.", code="no_access"
            )
        return ctx

    return dep


def area_any_status(name: str) -> Callable[..., Awaitable[Ctx]]:
    """Like ``area`` but also during sign-up and without a valid subscription (billing pages,
    onboarding): the person must still be able to pay or finish."""

    async def dep(ctx: MemberCtx) -> Ctx:
        if not ctx.can(name):
            raise Forbidden(
                "Seu departamento não tem acesso a esta área. Peça à Diretoria.", code="no_access"
            )
        return ctx

    return dep


async def require_admin(request: Request, user: CurrentUser) -> User:
    """VIP Network team. ``viewer`` reads only."""
    if user.kind != "admin":
        raise Forbidden("Área restrita à equipe VIP Network.", code="wrong_area")
    role = user.admin_role or ("owner" if user.is_superuser else "admin")
    read_only_post = request.url.path.endswith("/admin/mail/preview")  # renders, changes nothing
    if (
        role == "viewer"
        and request.method.upper() not in ("GET", "HEAD", "OPTIONS")
        and not read_only_post
    ):
        raise Forbidden("Seu papel na equipe só permite visualizar.", code="read_only")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client else None

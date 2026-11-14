"""/auth: login (company and team), session refresh, register (step 2 of the sign-up), e-mail
verification, password reset and colleague activation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import Unauthorized
from app.modules.auth import service
from app.modules.auth.deps import CurrentUser, DbSession, client_ip
from app.modules.billing.models import Subscription
from app.modules.mail import service as mail
from app.modules.organizations import service as orgs
from app.modules.organizations.models import Organization
from app.modules.organizations.views import me_view

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    cnpj: str
    full_name: str = Field(min_length=3, max_length=120)
    job_title: str = Field(default="", max_length=80)
    email: str
    phone: str = Field(default="", max_length=30)
    password: str
    cnpj_relation: str = "socio"
    invite_code: str | None = None


class PasswordIn(BaseModel):
    password: str
    password_confirm: str


class ForgotIn(BaseModel):
    email: str


class MeIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    job_title: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    notification_prefs: dict[str, Any] | None = None


def _set_cookie(response: Response, raw: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.refresh_cookie_name,
        raw,
        max_age=s.jwt_refresh_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


async def _me(session: DbSession, user: Any) -> dict[str, Any]:
    org = await session.get(Organization, user.org_id) if user.org_id else None
    sub = None
    if org is not None:
        sub = (
            await session.execute(select(Subscription).where(Subscription.org_id == org.id))
        ).scalar_one_or_none()
    return me_view(user, org, sub)


async def _login(
    session: DbSession, request: Request, response: Response, body: LoginIn, kind: str
) -> dict[str, Any]:
    user = await service.authenticate(session, body.email, body.password, kind=kind)
    access, expires_in, raw = await service.open_session(
        session, user, user_agent=request.headers.get("user-agent"), ip=client_ip(request)
    )
    _set_cookie(response, raw)
    return {"access_token": access, "expires_in": expires_in, **await _me(session, user)}


@router.post("/login")
async def login(
    body: LoginIn, request: Request, response: Response, session: DbSession
) -> dict[str, Any]:
    return await _login(session, request, response, body, "member")


@router.post("/admin/login")
async def admin_login(
    body: LoginIn, request: Request, response: Response, session: DbSession
) -> dict[str, Any]:
    return await _login(session, request, response, body, "admin")


@router.post("/refresh")
async def refresh(request: Request, response: Response, session: DbSession) -> dict[str, Any]:
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    if not raw:
        raise Unauthorized("Entre para continuar.", code="refresh_missing")
    user, access, expires_in, new_raw = await service.rotate(
        session, raw, user_agent=request.headers.get("user-agent"), ip=client_ip(request)
    )
    _set_cookie(response, new_raw)
    return {"access_token": access, "expires_in": expires_in, **await _me(session, user)}


@router.post("/logout")
async def logout(request: Request, response: Response, session: DbSession) -> dict[str, bool]:
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    if raw:
        await service.close_session(session, raw)
    response.delete_cookie(get_settings().refresh_cookie_name, path="/api/v1/auth")
    return {"ok": True}


@router.get("/me")
async def me(user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await _me(session, user)


@router.patch("/me")
async def update_me(body: MeIn, user: CurrentUser, session: DbSession) -> dict[str, Any]:
    for key in ("full_name", "job_title", "phone"):
        value = getattr(body, key)
        if value is not None:
            setattr(user, key, value.strip())
    if body.notification_prefs is not None:
        user.notification_prefs = body.notification_prefs
    return await _me(session, user)


@router.post("/register")
async def register(
    body: RegisterIn, request: Request, response: Response, session: DbSession
) -> dict[str, Any]:
    """Step 2 of the sign-up: company (pending) + owner, then signed in."""
    user, _org = await orgs.register(
        session,
        cnpj=body.cnpj,
        full_name=body.full_name,
        job_title=body.job_title,
        email=body.email,
        phone=body.phone,
        password=body.password,
        cnpj_relation=body.cnpj_relation,
        invite_code=body.invite_code,
    )
    access, expires_in, raw = await service.open_session(
        session, user, user_agent=request.headers.get("user-agent"), ip=client_ip(request)
    )
    _set_cookie(response, raw)
    return {"access_token": access, "expires_in": expires_in, **await _me(session, user)}


@router.post("/verify/{token}")
async def verify(token: str, session: DbSession) -> dict[str, bool]:
    await orgs.verify_email(session, token)
    return {"ok": True}


@router.post("/verify-resend")
async def verify_resend(user: CurrentUser, session: DbSession) -> dict[str, bool]:
    await orgs.resend_verification(session, user)
    return {"ok": True}


@router.post("/password/forgot")
async def forgot(body: ForgotIn, session: DbSession) -> dict[str, bool]:
    """Always answers ok (never reveals whether the e-mail has an account)."""
    try:
        email = service.normalize_email(body.email)
    except Exception:  # noqa: BLE001
        return {"ok": True}
    user = await service.get_by_email(session, email)
    if user is not None and user.status == "active":
        token = await service.issue_link(session, user, "reset")
        await mail.trigger(
            session, "auth.password_reset", user=user, link=f"/redefinir-senha/{token}"
        )
    return {"ok": True}


@router.post("/password/reset/{token}")
async def reset(token: str, body: PasswordIn, session: DbSession) -> dict[str, Any]:
    if body.password != body.password_confirm:
        from app.core.errors import AppError

        raise AppError("As senhas não conferem.", code="password_mismatch")
    row, user = await service.peek_link(session, token, "reset")
    service.validate_password(body.password)
    await service.consume_link(session, row)
    await service.set_password(session, user, body.password)
    return {"ok": True, "kind": user.kind}


@router.get("/activate/{token}")
async def activation_info(token: str, session: DbSession) -> dict[str, Any]:
    _row, user = await service.peek_link(session, token, "activate")
    org = await session.get(Organization, user.org_id) if user.org_id else None
    return {
        "email": user.email,
        "full_name": user.full_name,
        "org": org.display_name if org else "",
    }


@router.post("/activate/{token}")
async def activate(
    token: str, body: PasswordIn, request: Request, response: Response, session: DbSession
) -> dict[str, Any]:
    if body.password != body.password_confirm:
        from app.core.errors import AppError

        raise AppError("As senhas não conferem.", code="password_mismatch")
    user = await orgs.activate_member(session, token, body.password)
    access, expires_in, raw = await service.open_session(
        session, user, user_agent=request.headers.get("user-agent"), ip=client_ip(request)
    )
    _set_cookie(response, raw)
    return {"access_token": access, "expires_in": expires_in, **await _me(session, user)}

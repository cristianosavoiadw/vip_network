"""Sign-up by CNPJ, onboarding (10 steps), company profile, team and departments (§4, §5, §13)."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.modules.auth import service as auth
from app.modules.auth.models import User
from app.modules.integrations.cnpj import service as cnpj_service
from app.modules.integrations.cnpj.schemas import CompanyInfo
from app.modules.integrations.cnpj.validation import format_cnpj, is_valid_cnpj, only_digits
from app.modules.invites import service as invites
from app.modules.mail import service as mail
from app.modules.organizations.models import AccessRequest, AiSuggestion, Department, Organization
from app.modules.organizations.permissions import BUILTIN_DEPARTMENTS
from app.modules.settings import service as settings_service

PALETTE = (
    "#2F4B7C",
    "#1F6F5C",
    "#3A3F9E",
    "#8A4B1E",
    "#2E7D4F",
    "#6B2E6F",
    "#7A2533",
    "#B0472A",
    "#1D7C8C",
    "#25507A",
    "#5B3E8E",
    "#946B12",
    "#0F2A55",
)
CNAE_SECTOR = (  # first two digits of the CNAE → sector shown in Descobrir filters
    (range(1, 4), "agro"),
    (range(5, 34), "industria"),
    (range(35, 40), "industria"),
    (range(41, 44), "industria"),
    (range(45, 48), "varejo"),
    (range(49, 54), "logistica"),
    (range(58, 64), "tecnologia"),
    (range(86, 89), "saude"),
)
ONBOARDING_STEPS = 10


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "empresa"


def sector_from_cnae(code: str) -> str:
    digits = only_digits(code)
    if len(digits) < 2:
        return "outros"
    head = int(digits[:2])
    for rng, sector in CNAE_SECTOR:
        if head in rng:
            return sector
    return "servicos"


async def _unique_slug(session: AsyncSession, base: str) -> str:
    slug, n = base, 1
    while (await session.execute(select(Organization.id).where(Organization.slug == slug))).first():
        n += 1
        slug = f"{base}-{n}"
    return slug


def official_from(info: CompanyInfo) -> dict[str, Any]:
    a = info.address
    return {
        "cnpj": info.cnpj_formatted,
        "legal_name": info.legal_name,
        "trade_name": info.trade_name,
        "cnae_code": info.cnae_code,
        "cnae_description": info.cnae_description,
        "legal_nature": info.legal_nature,
        "size": info.size_label,
        "status": info.status_text or ("Ativa" if info.is_active else "Inativa"),
        "founded": info.founded.isoformat() if info.founded else None,
        "address": f"{a.street}, {a.number}{' ' + a.complement if a.complement else ''} · {a.district}".strip(
            " ,·"
        ),
        "city": a.city,
        "state": a.state,
        "zip": a.zip,
        "phone": info.phone,
        "email": info.email,
        "source": info.source,
    }


async def lookup(session: AsyncSession, raw_cnpj: str) -> dict[str, Any]:
    """Step 1: official data + whether the CNPJ already has an account."""
    digits = only_digits(raw_cnpj)
    if not is_valid_cnpj(digits):
        raise cnpj_service.CnpjInvalid("CNPJ inválido. Confira os 14 dígitos.")
    existing = (
        await session.execute(select(Organization).where(Organization.cnpj == digits))
    ).scalar_one_or_none()
    if existing is not None and existing.status != "pending":
        return {"exists": True, "cnpj": format_cnpj(digits), "official": None}
    info = await cnpj_service.lookup(digits, session=session)
    return {"exists": False, "cnpj": info.cnpj_formatted, "official": official_from(info)}


async def register(
    session: AsyncSession,
    *,
    cnpj: str,
    full_name: str,
    job_title: str,
    email: str,
    phone: str,
    password: str,
    cnpj_relation: str,
    invite_code: str | None,
) -> tuple[User, Organization]:
    """Step 2: creates the company (pending) and its owner. Applies the access mode."""
    conf = await settings_service.get(session, "access")
    digits = only_digits(cnpj)
    if not is_valid_cnpj(digits):
        raise cnpj_service.CnpjInvalid("CNPJ inválido. Confira os 14 dígitos.")
    invite = None
    if invite_code:
        invite = await invites.validate(session, invite_code, email=email)
    elif conf["mode"] == "invite":
        raise Forbidden(
            "A VIP Network está aceitando apenas empresas convidadas.", code="invite_required"
        )
    if cnpj_relation not in ("socio", "diretoria", "autorizado"):
        raise AppError("Informe sua relação com a empresa.", code="relation_required")

    org = (
        await session.execute(select(Organization).where(Organization.cnpj == digits))
    ).scalar_one_or_none()
    if org is not None and org.status != "pending":
        raise Conflict(
            "Este CNPJ já tem conta na VIP Network. Peça acesso ao responsável.",
            code="cnpj_registered",
        )
    if org is not None:
        # an abandoned sign-up of the same CNPJ: only its own owner may resume it
        raise Conflict(
            "Já existe um cadastro em andamento para este CNPJ. Entre com o e-mail usado nele "
            "ou peça acesso ao responsável.",
            code="cnpj_pending",
        )
    info = await cnpj_service.lookup(digits, session=session)
    off = official_from(info)
    count = int(
        (await session.execute(select(func.count()).select_from(Organization))).scalar_one()
    )
    org = Organization(
        cnpj=digits,
        slug=await _unique_slug(session, slugify(info.trade_name or info.legal_name)),
        legal_name=info.legal_name,
        trade_name=info.trade_name or info.legal_name.title(),
        status="pending",
        official=off,
        official_fetched_at=datetime.now(UTC),
        cnae_main=only_digits(info.cnae_code),
        city=info.address.city,
        state=info.address.state,
        size=info.size_label,
        opened_on=info.founded,
        sector=sector_from_cnae(info.cnae_code),
        segment=(info.cnae_description or "")[:80],
        color=PALETTE[count % len(PALETTE)],
        onboarding_step=3,
    )
    session.add(org)
    await session.flush()
    for slug, name in BUILTIN_DEPARTMENTS:
        session.add(Department(org_id=org.id, slug=slug, name=name, builtin=True))
    user = await auth.create_user(
        session,
        email=email,
        password=password,
        org_id=org.id,
        is_org_owner=True,
        departments=["diretoria"],
        full_name=full_name,
        job_title=job_title,
        phone=phone,
        cnpj_relation=cnpj_relation,
    )
    if invite is not None:
        await invites.accept(session, invite, org)
    token = await auth.issue_link(session, user, "verify")
    await mail.trigger(
        session,
        "auth.verify_email",
        user=user,
        variables={"empresa": org.display_name},
        link=f"/confirmar-email/{token}",
    )
    return user, org


async def request_access(
    session: AsyncSession, *, cnpj: str, full_name: str, email: str, job_title: str
) -> None:
    """A CNPJ that already has an account: ask the owner, never take the company over."""
    from app.modules.notifications import service as notifications

    digits = only_digits(cnpj)
    org = (
        await session.execute(select(Organization).where(Organization.cnpj == digits))
    ).scalar_one_or_none()
    if org is None or org.status == "pending":
        raise NotFound("Não encontramos uma conta para este CNPJ.", code="org_not_found")
    address = auth.normalize_email(email)
    dup = (
        await session.execute(
            select(AccessRequest.id).where(
                AccessRequest.org_id == org.id,
                AccessRequest.email == address,
                AccessRequest.status == "pending",
            )
        )
    ).first()
    if dup:
        return
    req = AccessRequest(
        org_id=org.id, email=address, full_name=full_name.strip(), job_title=job_title.strip()
    )
    session.add(req)
    await session.flush()
    await notifications.notify(
        session,
        org.id,
        kind="org.access_request",
        title=f"{req.full_name or address} pediu acesso à empresa",
        link="/app/equipe",
        departments=("diretoria",),
        email_vars={"solicitante": req.full_name or address, "email_solicitante": address},
    )


async def decide_access(
    session: AsyncSession,
    org: Organization,
    req_id: uuid.UUID,
    *,
    approve: bool,
    departments: list[str],
    decided_by: User,
) -> AccessRequest:
    req = await session.get(AccessRequest, req_id)
    if req is None or req.org_id != org.id:
        raise NotFound("Pedido não encontrado.")
    if req.status != "pending":
        raise AppError("Este pedido já foi respondido.", code="already_decided")
    req.status = "approved" if approve else "denied"
    req.decided_by = decided_by.id
    req.decided_at = datetime.now(UTC)
    if approve:
        await invite_member(
            session,
            org,
            decided_by,
            email=req.email,
            full_name=req.full_name,
            departments=departments or ["comercial"],
            key="org.access_granted",
        )
    return req


async def verify_email(session: AsyncSession, token: str) -> User:
    row, user = await auth.peek_link(session, token, "verify")
    await auth.consume_link(session, row)
    user.email_verified_at = datetime.now(UTC)
    return user


async def resend_verification(session: AsyncSession, user: User) -> None:
    if user.email_verified_at:
        return
    org = await session.get(Organization, user.org_id) if user.org_id else None
    token = await auth.issue_link(session, user, "verify")
    await mail.trigger(
        session,
        "auth.verify_email",
        user=user,
        variables={"empresa": org.display_name if org else ""},
        link=f"/confirmar-email/{token}",
    )


# ------------------------------------------------------------------ onboarding & profile

PROFILE_FIELDS = (
    "trade_name",
    "sector",
    "segment",
    "description",
    "website",
    "coverage",
    "differentials",
    "contacts",
    "certifications",
    "logo_url",
    "cover_url",
    "goals",
)


async def update_profile(
    session: AsyncSession, org: Organization, data: dict[str, Any]
) -> Organization:
    for key in PROFILE_FIELDS:
        if key in data and data[key] is not None:
            value = data[key]
            if isinstance(value, str):
                value = value.strip()
            if key == "description":
                org.description_source = "manual"
            setattr(org, key, value)
    if not org.trade_name:
        org.trade_name = org.legal_name.title()
    return org


async def set_step(org: Organization, step: int) -> None:
    if not 1 <= step <= ONBOARDING_STEPS:
        raise AppError("Etapa inválida.", code="invalid_step")
    if org.onboarding_completed_at is None:
        org.onboarding_step = max(org.onboarding_step, step)


async def complete_onboarding(session: AsyncSession, org: Organization, user: User) -> Organization:
    from app.modules.billing.entitlement import entitled
    from app.modules.billing.models import PRICES_CENTS
    from app.modules.billing.service import brl, get_subscription

    if org.onboarding_completed_at is not None:
        return org
    sub = await get_subscription(session, org.id)
    if not entitled(sub):
        raise AppError("Cadastre o cartão para começar.", code="subscription_required")
    org.status = "active"
    org.discoverable = True
    org.onboarding_step = ONBOARDING_STEPS
    org.onboarding_completed_at = datetime.now(UTC)
    if sub and sub.kind == "standard" and sub.trial_end:
        await mail.trigger(
            session,
            "billing.trial_started",
            user=user,
            variables={
                "empresa": org.display_name,
                "fim_do_teste": sub.trial_end.astimezone().strftime("%d/%m/%Y às %H:%M"),
                "valor": brl(PRICES_CENTS[sub.plan]),
            },
            link="/app/descobrir",
        )
    await invites.notify_accepted(session, org)
    return org


def suggest_description(org: Organization, offers: list[str]) -> str:
    """Local suggestion from official data and the catalog (CompanyProfileAgent on WeOS
    replaces it when configured). Always waits for human approval."""
    off = org.official or {}
    since = f" desde {org.opened_on.year}" if org.opened_on else ""
    place = f" em {org.city} ({org.state})" if org.city else ""
    activity = (off.get("cnae_description") or org.segment or "atividade empresarial").rstrip(".")
    text = f"{org.display_name} atua com {activity.lower()}{place}{since}."
    if offers:
        text += " Oferece " + ", ".join(offers[:4]).lower() + "."
    if org.coverage:
        text += f" Atende {org.coverage}."
    return text


async def create_description_suggestion(session: AsyncSession, org: Organization) -> AiSuggestion:
    from app.modules.catalog.models import Offer

    offers = [
        o.name
        for o in (
            await session.execute(
                select(Offer).where(Offer.org_id == org.id, Offer.status == "published")
            )
        ).scalars()
    ]
    await session.execute(
        AiSuggestion.__table__.update()
        .where(
            AiSuggestion.org_id == org.id,
            AiSuggestion.field == "description",
            AiSuggestion.status == "pending",
        )
        .values(status="rejected")
    )
    sug = AiSuggestion(org_id=org.id, field="description", value=suggest_description(org, offers))
    session.add(sug)
    await session.flush()
    return sug


async def decide_suggestion(
    session: AsyncSession, org: Organization, sug_id: uuid.UUID, *, approve: bool, value: str | None
) -> AiSuggestion:
    sug = await session.get(AiSuggestion, sug_id)
    if sug is None or sug.org_id != org.id:
        raise NotFound("Sugestão não encontrada.")
    if sug.status != "pending":
        raise AppError("Esta sugestão já foi respondida.", code="already_decided")
    sug.status = "approved" if approve else "rejected"
    if approve and sug.field == "description":
        org.description = (value or sug.value).strip()
        org.description_source = "ai"
    return sug


# ------------------------------------------------------------------ team & departments


async def team(session: AsyncSession, org_id: uuid.UUID) -> list[User]:
    return list(
        (
            await session.execute(
                select(User)
                .where(User.org_id == org_id, User.kind == "member")
                .order_by(User.created_at)
            )
        ).scalars()
    )


async def departments(session: AsyncSession, org_id: uuid.UUID) -> list[Department]:
    return list(
        (
            await session.execute(
                select(Department)
                .where(Department.org_id == org_id)
                .order_by(Department.builtin.desc(), Department.created_at)
            )
        ).scalars()
    )


async def _check_departments(
    session: AsyncSession, org_id: uuid.UUID, slugs: list[str]
) -> list[str]:
    valid = {d.slug for d in await departments(session, org_id)}
    clean = [s for s in dict.fromkeys(slugs) if s in valid]
    if not clean:
        raise AppError("Escolha pelo menos um departamento.", code="departments_required")
    return clean


async def invite_member(
    session: AsyncSession,
    org: Organization,
    by: User,
    *,
    email: str,
    full_name: str,
    departments: list[str],
    key: str = "team.invite",
) -> User:
    depts = await _check_departments(session, org.id, departments)
    user = await auth.create_user(
        session,
        email=email,
        password=None,
        org_id=org.id,
        departments=depts,
        full_name=full_name,
        status="pending",
    )
    token = await auth.issue_link(session, user, "activate")
    names = {d.slug: d.name for d in await departments_by_slug(session, org.id)}
    await mail.trigger(
        session,
        key,
        user=user,
        variables={
            "empresa": org.display_name,
            "quem_convidou": by.full_name or org.display_name,
            "departamento": ", ".join(names.get(s, s) for s in depts),
        },
        link=f"/ativar/{token}",
    )
    return user


async def departments_by_slug(session: AsyncSession, org_id: uuid.UUID) -> list[Department]:
    return await departments(session, org_id)


async def update_member(
    session: AsyncSession,
    org: Organization,
    user_id: uuid.UUID,
    *,
    departments: list[str] | None,
    blocked: bool | None,
    actor: User,
) -> User:
    user = await session.get(User, user_id)
    if user is None or user.org_id != org.id:
        raise NotFound("Pessoa não encontrada na equipe.")
    if user.is_org_owner and user.id != actor.id and blocked:
        raise Forbidden("Não dá para bloquear o responsável pela conta.", code="owner")
    if departments is not None:
        user.departments = await _check_departments(session, org.id, departments)
    if blocked is not None and user.id != actor.id:
        user.status = "blocked" if blocked else ("active" if user.password_hash else "pending")
        if blocked:
            await auth.revoke_all(session, user.id)
    return user


async def remove_member(
    session: AsyncSession, org: Organization, user_id: uuid.UUID, actor: User
) -> None:
    user = await session.get(User, user_id)
    if user is None or user.org_id != org.id:
        raise NotFound("Pessoa não encontrada na equipe.")
    if user.is_org_owner:
        raise Forbidden("Não dá para remover o responsável pela conta.", code="owner")
    user.org_id = None
    user.status = "blocked"
    user.departments = []
    await auth.revoke_all(session, user.id)


async def add_department(session: AsyncSession, org: Organization, name: str) -> Department:
    name = name.strip()
    if not name:
        raise AppError("Dê um nome ao departamento.", code="name_required")
    slug = slugify(name)[:40]
    if (
        await session.execute(
            select(Department.id).where(Department.org_id == org.id, Department.slug == slug)
        )
    ).first():
        raise Conflict("Já existe um departamento com esse nome.", code="department_exists")
    dept = Department(org_id=org.id, slug=slug, name=name[:80], builtin=False)
    session.add(dept)
    await session.flush()
    return dept


async def delete_department(session: AsyncSession, org: Organization, dept_id: uuid.UUID) -> None:
    dept = await session.get(Department, dept_id)
    if dept is None or dept.org_id != org.id:
        raise NotFound("Departamento não encontrado.")
    if dept.builtin:
        raise Forbidden("Os departamentos padrão não podem ser apagados.", code="builtin")
    for user in await team(session, org.id):
        if dept.slug in (user.departments or []):
            user.departments = [d for d in user.departments if d != dept.slug] or ["comercial"]
    await session.delete(dept)


async def activate_member(session: AsyncSession, token: str, password: str) -> User:
    row, user = await auth.peek_link(session, token, "activate")
    auth.validate_password(password)
    await auth.consume_link(session, row)
    await auth.set_password(session, user, password)
    user.status = "active"
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    return user

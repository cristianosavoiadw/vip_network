"""VIP invitations (owner decision 2026-11-14).

- Access mode ``invite``: only invited companies sign up (closed club); VIP plan = 12 months and
  nothing is charged after it (renewal by platform rules, to be defined).
- ``paid``: invitations are off; anyone subscribes with the 7-day trial.
- ``both``: anyone subscribes; invited companies enter on the VIP plan for ``vip_months`` and
  are charged the chosen plan after it.

Each company that entered by invitation (or every company, when ``who_invites = all``) can
invite ``invites_per_member`` companies; an expired or revoked invite goes back to the inviter
when ``return_expired``. The team panel issues invites without a limit.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.modules.auth.models import User
from app.modules.invites.models import Invite
from app.modules.mail import service as mail
from app.modules.organizations.models import Organization
from app.modules.settings import service as settings_service

log = logging.getLogger("vip.invites")
_ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"


def new_code() -> str:
    part = lambda: "".join(secrets.choice(_ALPHABET) for _ in range(4))  # noqa: E731
    return f"VIP-{part()}-{part()}"


async def access(session: AsyncSession) -> dict[str, Any]:
    return await settings_service.get(session, "access")


def _counts_as_used(inv: Invite, conf: dict[str, Any]) -> bool:
    if inv.status in ("pending", "accepted"):
        return True
    return not conf["return_expired"] and inv.status in ("expired", "revoked")


async def eligible(session: AsyncSession, org: Organization) -> bool:
    conf = await access(session)
    if conf["mode"] == "paid":
        return False
    return org.entry == "invite" or conf["who_invites"] == "all"


async def summary(session: AsyncSession, org: Organization) -> dict[str, Any]:
    conf = await access(session)
    rows = list(
        (
            await session.execute(
                select(Invite)
                .where(Invite.inviter_org_id == org.id)
                .order_by(Invite.created_at.desc())
            )
        ).scalars()
    )
    can = await eligible(session, org)
    used = sum(1 for r in rows if _counts_as_used(r, conf))
    return {
        "enabled": can,
        "mode": conf["mode"],
        "per_member": conf["invites_per_member"],
        "remaining": max(0, conf["invites_per_member"] - used) if can else 0,
        "ttl_days": conf["invite_ttl_days"],
        "bind_email": conf["bind_email"],
        "return_expired": conf["return_expired"],
        "vip_months": settings_service.vip_months(conf),
        "invites": rows,
    }


async def _check_target(session: AsyncSession, email: str) -> str:
    """The e-mail is what identifies an invite (owner decision 2026-11-14): no account with
    it yet and no other invite waiting for it."""
    from app.modules.auth.models import User
    from app.modules.auth.service import normalize_email

    address = normalize_email(email)
    if (await session.execute(select(User.id).where(User.email == address))).first():
        raise Conflict("Este e-mail já tem conta na VIP Network.", code="already_member")
    pending = (
        await session.execute(
            select(Invite.id).where(Invite.email == address, Invite.status == "pending")
        )
    ).first()
    if pending:
        raise Conflict("Este e-mail já tem um convite aguardando cadastro.", code="already_invited")
    return address


def _clean_name(value: str, label: str) -> str:
    value = " ".join((value or "").split())[:80]
    if len(value) < 2:
        raise AppError(f"Informe o {label}.", code="name_required")
    return value


async def _send(session: AsyncSession, inv: Invite, inviter_name: str) -> None:
    conf = await access(session)
    months = settings_service.vip_months(conf)
    tz_date = inv.expires_at.astimezone().strftime("%d/%m/%Y")
    await mail.trigger(
        session,
        # the team's invite has its own institutional e-mail; a company's invite names it
        "invite.staff" if inv.by_staff else "invite.sent",
        to=inv.email,
        variables={
            "primeiro_nome": inv.first_name,
            "quem_convidou": inviter_name,
            "empresa": inv.company_name or "sua empresa",
            "mensagem": inv.message,
            "validade_vip": f"{months} meses",
            "convites": str(conf["invites_per_member"]),
            "expira_em": tz_date,
        },
        link=f"/convite/{inv.code}",
    )


async def create(
    session: AsyncSession,
    *,
    org: Organization | None,
    user: User | None,
    first_name: str,
    last_name: str,
    company_name: str,
    email: str,
    message: str = "",
    by_staff: bool = False,
) -> Invite:
    conf = await access(session)
    if conf["mode"] == "paid":
        raise Forbidden("Convites estão desativados no momento.", code="invites_off")
    if not by_staff:
        if org is None or not await eligible(session, org):
            raise Forbidden("Seu plano não inclui convites.", code="not_eligible")
        if (await summary(session, org))["remaining"] <= 0:
            raise Forbidden("Você já usou todos os seus convites.", code="no_invites_left")
    first = _clean_name(first_name, "nome")
    last = _clean_name(last_name, "sobrenome")
    company = " ".join((company_name or "").split())[:160]
    if len(company) < 2:
        raise AppError("Informe o nome da empresa.", code="company_required")
    address = await _check_target(session, email)
    inv = Invite(
        code=new_code(),
        inviter_org_id=None if by_staff else org.id,  # type: ignore[union-attr]
        inviter_user_id=user.id if user else None,
        by_staff=by_staff,
        first_name=first,
        last_name=last,
        company_name=company,
        email=address,
        message=message.strip()[:600],
        expires_at=datetime.now(UTC) + timedelta(days=int(conf["invite_ttl_days"])),
    )
    session.add(inv)
    await session.flush()
    await _send(session, inv, "Equipe VIP Network" if by_staff else org.display_name)  # type: ignore[union-attr]
    return inv


async def get_own(session: AsyncSession, org_id: uuid.UUID, invite_id: uuid.UUID) -> Invite:
    inv = await session.get(Invite, invite_id)
    if inv is None or inv.inviter_org_id != org_id:
        raise NotFound("Convite não encontrado.")
    return inv


async def revoke(session: AsyncSession, inv: Invite) -> Invite:
    if inv.status != "pending":
        raise AppError(
            "Só dá para cancelar um convite que ainda aguarda cadastro.", code="not_pending"
        )
    inv.status = "revoked"
    return inv


async def resend(session: AsyncSession, inv: Invite, inviter_name: str) -> Invite:
    if inv.status != "pending":
        raise AppError("Este convite não está mais aguardando cadastro.", code="not_pending")
    await _send(session, inv, inviter_name)
    return inv


async def by_code(session: AsyncSession, code: str) -> Invite | None:
    return (
        await session.execute(select(Invite).where(Invite.code == code.strip().upper()))
    ).scalar_one_or_none()


async def validate(session: AsyncSession, code: str, *, email: str | None = None) -> Invite:
    conf = await access(session)
    if conf["mode"] == "paid":
        raise Forbidden("Convites estão desativados no momento.", code="invites_off")
    inv = await by_code(session, code)
    if inv is None:
        raise NotFound(
            "Código de convite não encontrado. Confira e tente de novo.", code="invite_not_found"
        )
    if inv.status == "pending" and inv.expires_at <= datetime.now(UTC):
        inv.status = "expired"
    if inv.status != "pending":
        msg = {
            "accepted": "Este convite já foi usado.",
            "expired": "Este convite expirou. Peça um novo a quem convidou.",
            "revoked": "Este convite foi cancelado por quem convidou.",
        }[inv.status]
        raise AppError(msg, code=f"invite_{inv.status}")
    if email is not None and conf["bind_email"] and email.strip().lower() != inv.email:
        raise AppError(
            "Este convite foi enviado para outro e-mail. Cadastre-se com o e-mail que recebeu "
            "o convite.",
            code="invite_other_email",
        )
    return inv


async def public_view(session: AsyncSession, inv: Invite) -> dict[str, Any]:
    conf = await access(session)
    inviter = await session.get(Organization, inv.inviter_org_id) if inv.inviter_org_id else None
    return {
        "code": inv.code,
        "inviter": inviter.display_name if inviter else "Equipe VIP Network",
        "inviter_color": inviter.color if inviter else "#0B1630",
        "company_name": inv.company_name,
        "first_name": inv.first_name,
        "last_name": inv.last_name,
        "email": inv.email,
        "bind_email": conf["bind_email"],
        "expires_at": inv.expires_at.isoformat(),
        "vip_months": settings_service.vip_months(conf),
        "invites_per_member": conf["invites_per_member"],
        "mode": conf["mode"],
    }


async def accept(session: AsyncSession, inv: Invite, org: Organization) -> None:
    inv.status = "accepted"
    inv.accepted_org_id = org.id
    inv.accepted_at = datetime.now(UTC)
    org.entry = "invite"
    org.invited_by_org_id = inv.inviter_org_id


async def notify_accepted(session: AsyncSession, org: Organization) -> None:
    """Called when the invited company finishes the sign-up."""
    if not org.invited_by_org_id:
        return
    from app.modules.notifications import service as notifications

    await notifications.notify(
        session,
        org.invited_by_org_id,
        kind="invite.accepted",
        title=f"{org.display_name} entrou na rede pelo seu convite",
        link=f"/app/empresas/{org.slug}",
        departments=("diretoria",),
        email_vars={"empresa_origem": org.display_name},
    )


async def staff_list(session: AsyncSession, *, status: str | None = None) -> list[dict[str, Any]]:
    q = select(Invite).order_by(Invite.created_at.desc()).limit(500)
    if status:
        q = q.where(Invite.status == status)
    rows = list((await session.execute(q)).scalars())
    names: dict[uuid.UUID, str] = {}
    ids = {r.inviter_org_id for r in rows if r.inviter_org_id} | {
        r.accepted_org_id for r in rows if r.accepted_org_id
    }
    if ids:
        for o in (
            await session.execute(select(Organization).where(Organization.id.in_(ids)))
        ).scalars():
            names[o.id] = o.display_name
    return [
        {
            "id": str(r.id),
            "code": r.code,
            "first_name": r.first_name,
            "last_name": r.last_name,
            "email": r.email,
            "company_name": (names.get(r.accepted_org_id) if r.accepted_org_id else None)
            or r.company_name,
            "inviter": names.get(r.inviter_org_id, "Equipe VIP Network")
            if r.inviter_org_id
            else "Equipe VIP Network",
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
            "expires_at": r.expires_at.isoformat(),
        }
        for r in rows
    ]


async def tree(session: AsyncSession) -> list[dict[str, Any]]:
    """Who invited whom: nodes {id, name, invited_by, used, per_member}."""
    conf = await access(session)
    orgs = list(
        (
            await session.execute(
                select(Organization).where(
                    (Organization.entry == "invite")
                    | Organization.id.in_(
                        select(Invite.inviter_org_id).where(Invite.inviter_org_id.is_not(None))
                    )
                )
            )
        ).scalars()
    )
    used_rows = (
        await session.execute(
            select(Invite.inviter_org_id, func.count())
            .where(Invite.status.in_(("pending", "accepted")))
            .group_by(Invite.inviter_org_id)
        )
    ).all()
    used = {k: int(v) for k, v in used_rows}
    return [
        {
            "id": str(o.id),
            "name": o.display_name,
            "color": o.color,
            "invited_by": str(o.invited_by_org_id) if o.invited_by_org_id else None,
            "used": used.get(o.id, 0),
            "per_member": conf["invites_per_member"],
        }
        for o in orgs
    ]


async def tick(session: AsyncSession) -> None:
    """Expire overdue invites (and tell the inviter) and remind 3 days before."""
    now = datetime.now(UTC)
    conf = await access(session)
    from app.modules.notifications import service as notifications

    overdue = (
        await session.execute(
            select(Invite).where(Invite.status == "pending", Invite.expires_at <= now)
        )
    ).scalars()
    for inv in overdue:
        inv.status = "expired"
        if inv.inviter_org_id:
            await notifications.notify(
                session,
                inv.inviter_org_id,
                kind="invite.expired",
                title=f"O convite para {inv.company_name or 'uma empresa'} expirou",
                link="/app/indicar",
                departments=("diretoria",),
                email_vars={
                    "empresa_origem": inv.company_name or "a empresa convidada",
                    "devolvido": "O convite voltou para você." if conf["return_expired"] else "",
                },
            )
    soon = (
        await session.execute(
            select(Invite).where(
                Invite.status == "pending",
                Invite.reminded_at.is_(None),
                Invite.expires_at <= now + timedelta(days=3),
                Invite.expires_at > now,
            )
        )
    ).scalars()
    for inv in soon:
        inviter = (
            await session.get(Organization, inv.inviter_org_id) if inv.inviter_org_id else None
        )
        await mail.trigger(
            session,
            "invite.reminder",
            to=inv.email,
            variables={
                "quem_convidou": inviter.display_name if inviter else "Equipe VIP Network",
                "empresa": inv.company_name or "sua empresa",
                "dias": str(max(1, (inv.expires_at - now).days)),
                "expira_em": inv.expires_at.astimezone().strftime("%d/%m/%Y"),
            },
            link=f"/convite/{inv.code}",
        )
        inv.reminded_at = now


async def tick_forever() -> None:
    from app.db.session import SessionLocal

    while True:
        try:
            async with SessionLocal() as session:
                await tick(session)
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("invites tick failed")
        await asyncio.sleep(600)


def invite_link(code: str) -> str:
    return f"{get_settings().frontend_url.rstrip('/')}/convite/{code}"

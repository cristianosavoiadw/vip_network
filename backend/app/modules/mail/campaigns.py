"""Campaigns: audiences, start, and the background step that queues their messages.

Manual campaigns queue every recipient once when they start (respecting suppressions); the
shared queue sends them within the caps. Automatic campaigns (sequences) are a list of
``steps`` [{"after_days": 1, "subject": .., "body_md": ..}] applied to people who enter the
audience; each person gets each step once (``ref`` in the message variables).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.billing.models import Subscription
from app.modules.mail import render
from app.modules.mail.models import EmailCampaign, EmailMessage, EmailSuppression
from app.modules.organizations.models import Organization

# key -> label (shown in the campaign form)
AUDIENCES: dict[str, str] = {
    "all": "Todos os usuários ativos",
    "subscribers": "Empresas assinantes",
    "trialing": "Em teste grátis",
    "vip": "Convidados VIP",
    "vip_expiring": "VIP vencendo em 30 dias",
    "incomplete": "Cadastro incompleto",
    "canceled": "Ex-assinantes",
}


def _audience_query(segment: str):  # noqa: ANN202
    q = select(User).where(User.kind == "member", User.status == "active")
    now = datetime.now(UTC)
    if segment == "all":
        return q
    q = q.join(Organization, Organization.id == User.org_id)
    if segment == "incomplete":
        return q.where(Organization.status == "pending")
    q = q.join(Subscription, Subscription.org_id == Organization.id)
    if segment == "subscribers":
        return q.where(Subscription.kind == "standard", Subscription.status == "active")
    if segment == "trialing":
        return q.where(Subscription.status == "trialing", Subscription.kind == "standard")
    if segment == "vip":
        return q.where(Subscription.kind == "vip", Subscription.vip_until > now)
    if segment == "vip_expiring":
        return q.where(
            Subscription.kind == "vip",
            and_(Subscription.vip_until > now, Subscription.vip_until <= now + timedelta(days=30)),
        )
    if segment == "canceled":
        return q.where(Subscription.status == "canceled")
    raise ValueError(segment)


async def audience_size(session: AsyncSession, segment: str) -> int:
    sub = _audience_query(segment).subquery()
    return int((await session.execute(select(func.count()).select_from(sub))).scalar_one())


async def _recipients(session: AsyncSession, segment: str) -> list[User]:
    suppressed = select(EmailSuppression.email)
    q = _audience_query(segment).where(User.email.not_in(suppressed))
    return list((await session.execute(q)).scalars().unique())


async def _org_name(session: AsyncSession, user: User) -> str:
    if user.org_id is None:
        return ""
    org = await session.get(Organization, user.org_id)
    return org.display_name if org else ""


def _message(
    camp: EmailCampaign, user: User, org_name: str, subject: str, body: str, ref: str = ""
) -> EmailMessage:
    from app.core.config import get_settings

    values: dict[str, Any] = {
        "primeiro_nome": (user.full_name.split() or [""])[0],
        "empresa": org_name,
        "link": get_settings().frontend_url.rstrip("/") + "/app",
    }
    return EmailMessage(
        campaign_id=camp.id,
        user_id=user.id,
        to_email=user.email,
        subject=render.subject(subject, values),
        variables={
            **values,
            "_body_md": body,
            "_preheader": render.fill(camp.preheader, values, escape=False),
            "_ref": ref,
        },
        token=secrets.token_urlsafe(24),
    )


async def start(session: AsyncSession, camp: EmailCampaign) -> int:
    """Freeze the content and queue one message per recipient."""
    recipients = await _recipients(session, camp.audience.get("segment", "all"))
    for user in recipients:
        session.add(
            _message(camp, user, await _org_name(session, user), camp.subject, camp.body_md)
        )
    camp.recipients = len(recipients)
    camp.status = "sending"
    camp.started_at = datetime.now(UTC)
    await session.flush()
    return len(recipients)


async def refresh_counters(session: AsyncSession, camp: EmailCampaign) -> None:
    rows = (
        await session.execute(
            select(
                func.count().filter(EmailMessage.status == "sent"),
                func.count().filter(EmailMessage.status == "failed"),
                func.count().filter(EmailMessage.status == "bounced"),
                func.count().filter(EmailMessage.opened_at.is_not(None)),
                func.count().filter(EmailMessage.clicked_at.is_not(None)),
                func.count().filter(EmailMessage.unsubscribed_at.is_not(None)),
                func.count().filter(EmailMessage.status == "queued"),
            ).where(EmailMessage.campaign_id == camp.id)
        )
    ).one()
    camp.sent, camp.failed, camp.bounced, camp.opened, camp.clicked, camp.unsubscribed = rows[:6]
    if camp.status == "sending" and rows[6] == 0:
        camp.status = "done"
        camp.finished_at = datetime.now(UTC)


async def _advance_sequence(session: AsyncSession, camp: EmailCampaign) -> None:
    now = datetime.now(UTC)
    recipients = await _recipients(session, camp.audience.get("segment", "incomplete"))
    for idx, step in enumerate(camp.steps or []):
        after = timedelta(days=int(step.get("after_days", 0)))
        for user in recipients:
            if user.created_at + after > now:
                continue
            ref = f"{camp.id}:{idx}"
            exists = (
                await session.execute(
                    select(EmailMessage.id).where(
                        EmailMessage.campaign_id == camp.id,
                        EmailMessage.user_id == user.id,
                        EmailMessage.variables["_ref"].astext == ref,
                    )
                )
            ).first()
            if exists:
                continue
            session.add(
                _message(
                    camp,
                    user,
                    await _org_name(session, user),
                    step.get("subject", camp.subject),
                    step.get("body_md", camp.body_md),
                    ref,
                )
            )


async def advance(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    due = (
        await session.execute(
            select(EmailCampaign).where(
                EmailCampaign.status == "scheduled", EmailCampaign.scheduled_at <= now
            )
        )
    ).scalars()
    for camp in due:
        await start(session, camp)
    active = (
        await session.execute(
            select(EmailCampaign).where(EmailCampaign.status.in_(("sending", "active")))
        )
    ).scalars()
    for camp in active:
        if camp.kind == "auto" and camp.status == "active":
            await _advance_sequence(session, camp)
        await refresh_counters(session, camp)

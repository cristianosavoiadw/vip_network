"""E-mail queue: every platform e-mail is a row in ``email_messages`` sent by the background
loop, respecting the hourly/daily caps. Triggers (``trigger()``) and campaigns share the queue.

The subject, preheader and body are frozen when the message is queued (an edit of the template
later does not change what is already waiting).
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mail
from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.mail import render
from app.modules.mail.models import EmailMessage, EmailSuppression, EmailTemplate
from app.modules.mail.triggers import BY_KEY, CAMPAIGN_TEMPLATES, TRIGGERS
from app.modules.settings import service as settings_service

log = logging.getLogger("vip.mail")
MAX_ATTEMPTS = 3
TICK_SECONDS = 20


def first_name(user: User | None) -> str:
    if user is None or not user.full_name:
        return ""
    return user.full_name.split()[0]


async def template_for(session: AsyncSession, key: str) -> EmailTemplate | None:
    return (
        await session.execute(select(EmailTemplate).where(EmailTemplate.system_key == key))
    ).scalar_one_or_none()


def _wants(user: User | None, key: str) -> bool:
    if user is None:
        return True
    prefs = (user.notification_prefs or {}).get("email") or {}
    return prefs.get(key, True) is not False


async def trigger(
    session: AsyncSession,
    key: str,
    *,
    to: str | None = None,
    user: User | None = None,
    variables: dict[str, Any] | None = None,
    link: str = "",
) -> EmailMessage | None:
    """Queue the e-mail of a platform event. Returns None when it is switched off, the user
    opted out, or the address is blocked (hard bounce / spam complaint)."""
    trig = BY_KEY.get(key)
    if trig is None:
        raise ValueError(f"unknown trigger {key}")
    address = (to or (user.email if user else "")).strip().lower()
    if not address:
        return None
    tpl = await template_for(session, key)
    if not trig.mandatory:
        if tpl is not None and not tpl.enabled:
            return None
        if tpl is None and not trig.default_on:
            return None
        if not _wants(user, key):
            return None
    blocked = await session.get(EmailSuppression, address)
    if blocked is not None and blocked.reason in ("bounce", "complaint"):
        return None
    base = get_settings().frontend_url.rstrip("/")
    values: dict[str, Any] = {"primeiro_nome": first_name(user), **(variables or {})}
    values["link"] = link if link.startswith("http") else f"{base}{link or '/app'}"
    subject_tpl = tpl.subject if tpl else trig.subject
    msg = EmailMessage(
        template_key=key,
        user_id=user.id if user else None,
        to_email=address,
        subject=render.subject(subject_tpl, values),
        variables={
            **values,
            "_body_md": tpl.body_md if tpl else trig.body,
            "_preheader": render.fill(
                tpl.preheader if tpl else trig.preheader, values, escape=False
            ),
            "_service": trig.mandatory,
        },
        token=secrets.token_urlsafe(24),
    )
    session.add(msg)
    await session.flush()
    return msg


def build(msg: EmailMessage) -> tuple[str, str]:
    """(html, text) of a queued message, with open/unsubscribe links signed by its token."""
    v = dict(msg.variables)
    body_md = str(v.pop("_body_md", ""))
    preheader = str(v.pop("_preheader", ""))
    service_mail = bool(v.pop("_service", False))
    api = get_settings().frontend_url.rstrip("/")
    inner = render.body_html(body_md, v)
    pixel = f'<img src="{api}/api/v1/mail/o/{msg.token}.gif" width="1" height="1" alt="">'
    if service_mail or msg.campaign_id is None:
        footer = (
            "E-mail de serviço da sua conta na VIP Network. Ajuste os avisos em "
            f'<a href="{api}/app/notificacoes" style="color:#5D6780">Preferências</a>.'
        )
    else:
        footer = (
            "Você recebe este e-mail por ser membro da VIP Network. "
            f'<a href="{api}/api/v1/mail/unsubscribe/{msg.token}" style="color:#5D6780">'
            "Descadastrar</a>."
        )
    html = render.wrap(inner + pixel, preheader=preheader, footer=footer)
    return html, render.body_text(body_md, v)


async def _sent_since(session: AsyncSession, since: datetime) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(EmailMessage).where(EmailMessage.sent_at >= since)
            )
        ).scalar_one()
    )


async def caps(session: AsyncSession) -> tuple[int, int]:
    conf = await settings_service.get(session, "mail")
    s = get_settings()
    return int(conf.get("hourly_cap") or s.mail_hourly_cap), int(
        conf.get("daily_cap") or s.mail_daily_cap
    )


async def send_queued(session: AsyncSession, *, limit: int = 50) -> int:
    """Send what is waiting, service e-mails first, within the hourly and daily caps."""
    now = datetime.now(UTC)
    hourly, daily = await caps(session)
    room = min(
        hourly - await _sent_since(session, now - timedelta(hours=1)),
        daily - await _sent_since(session, now - timedelta(days=1)),
        limit,
    )
    if room <= 0:
        return 0
    rows = (
        (
            await session.execute(
                select(EmailMessage)
                .where(EmailMessage.status == "queued")
                .order_by(EmailMessage.campaign_id.is_not(None), EmailMessage.created_at)
                .limit(room)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    sent = 0
    for msg in rows:
        html, text = build(msg)
        msg.attempts += 1
        try:
            await mail.send_mail(to=msg.to_email, subject=msg.subject, text=text, html=html)
        except mail.MailError as exc:
            msg.error = str(exc)[:300]
            if msg.attempts >= MAX_ATTEMPTS:
                msg.status = "failed"
            continue
        msg.status = "sent"
        msg.sent_at = datetime.now(UTC)
        msg.error = ""
        sent += 1
    return sent


async def seed_templates(session: AsyncSession) -> int:
    """Create the missing system templates (one per trigger) and, the first time, the campaign
    templates. Never overwrites an edited template."""
    existing = set(
        (
            await session.execute(
                select(EmailTemplate.system_key).where(EmailTemplate.system_key.is_not(None))
            )
        ).scalars()
    )
    created = 0
    for t in TRIGGERS:
        if t.key in existing:
            continue
        session.add(
            EmailTemplate(
                system_key=t.key,
                name=t.name,
                subject=t.subject,
                preheader=t.preheader,
                body_md=t.body,
                kind="system",
                enabled=t.default_on,
            )
        )
        created += 1
    has_campaign = (
        await session.execute(select(EmailTemplate.id).where(EmailTemplate.kind == "campaign"))
    ).first()
    if not has_campaign:
        for name, subj, body in CAMPAIGN_TEMPLATES:
            session.add(EmailTemplate(name=name, subject=subj, body_md=body, kind="campaign"))
            created += 1
    await session.flush()
    return created


async def tick(session: AsyncSession) -> None:
    from app.modules.mail import campaigns

    await campaigns.advance(session)
    await send_queued(session)


async def tick_forever() -> None:
    from app.db.session import SessionLocal

    while True:
        try:
            async with SessionLocal() as session:
                await tick(session)
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("mail tick failed")
        await asyncio.sleep(TICK_SECONDS)


async def suppress(session: AsyncSession, email: str, reason: str) -> None:
    address = email.strip().lower()
    if await session.get(EmailSuppression, address) is None:
        session.add(EmailSuppression(email=address, reason=reason, created_at=datetime.now(UTC)))


def new_token() -> str:
    return secrets.token_urlsafe(24)


__all__ = ["build", "seed_templates", "send_queued", "suppress", "trigger", "uuid"]

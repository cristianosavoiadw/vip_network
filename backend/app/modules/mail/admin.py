"""/admin/mail: Admin › E-mails e campanhas (tabs Disparos automáticos, Modelos, Campanhas,
Mensagens, Configuração). Built on the engine in ``service.py`` / ``campaigns.py``; same
behavior as BR Licitar's Marketing.

Pausing a campaign moves its queued messages to ``paused`` (the queue only sends ``queued``);
resuming puts them back.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update

from app.core import mail as core_mail
from app.core.errors import AppError, Conflict, NotFound
from app.modules.analytics.service import SP, count, rate
from app.modules.auth import service as auth
from app.modules.auth.deps import AdminUser, DbSession
from app.modules.mail import campaigns, render, service
from app.modules.mail.models import EmailCampaign, EmailMessage, EmailSuppression, EmailTemplate
from app.modules.mail.triggers import BY_KEY, GROUPS, SAMPLE, TRIGGERS, VARIABLES
from app.modules.organizations.views import iso
from app.modules.settings import service as settings_service

router = APIRouter(prefix="/admin/mail", tags=["admin"])

STATUS_LABELS = {
    "queued": "Na fila",
    "paused": "Pausado",
    "sent": "Entregue",
    "failed": "Falha",
    "bounced": "Devolvido",
    "suppressed": "Suprimido",
    "opened": "Aberto",
    "clicked": "Clicado",
    "unsubscribed": "Descadastrou",
}
CAMPAIGN_LABELS = {
    "draft": "Rascunho",
    "scheduled": "Agendada",
    "sending": "Enviando",
    "done": "Concluída",
    "paused": "Pausada",
    "active": "Ativa",
}
SUPPRESSION_LABELS = {
    "unsubscribed": "Descadastrados de campanhas",
    "bounce": "Devoluções permanentes",
    "complaint": "Marcaram como spam",
}


# ------------------------------------------------------------------ helpers


def mask_email(address: str) -> str:
    """``marina@andrade.com.br`` → ``ma***@andrade.com.br``."""
    local, _, domain = address.partition("@")
    return f"{local[:2]}***@{domain}" if domain else "***"


def _today_start() -> datetime:
    local = datetime.now(UTC).astimezone(SP)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def _sample_message(
    subject: str, preheader: str, body_md: str, *, system: bool, to: str = "preview@vip"
) -> EmailMessage:
    """A transient message (never added to the session) rendered exactly like the queue does."""
    return EmailMessage(
        campaign_id=None if system else uuid.uuid4(),
        to_email=to,
        subject=render.subject(subject, SAMPLE),
        variables={
            **SAMPLE,
            "_body_md": body_md,
            "_preheader": render.fill(preheader, SAMPLE, escape=False),
            "_service": system,
        },
        token="preview",
    )


async def _ensure_templates(session: DbSession) -> None:
    has = (
        await session.execute(select(EmailTemplate.id).where(EmailTemplate.system_key.is_not(None)))
    ).first()
    if not has or len(TRIGGERS) > await count(
        session,
        select(func.count()).select_from(EmailTemplate).where(EmailTemplate.kind == "system"),
    ):
        await service.seed_templates(session)


def _trigger_enabled(key: str, tpl: EmailTemplate | None) -> bool:
    trig = BY_KEY[key]
    if trig.mandatory:
        return True
    return tpl.enabled if tpl is not None else trig.default_on


def _template_view(t: EmailTemplate, *, full: bool = False) -> dict[str, Any]:
    trig = BY_KEY.get(t.system_key or "")
    out: dict[str, Any] = {
        "id": str(t.id),
        "name": t.name,
        "kind": t.kind,
        "system_key": t.system_key,
        "subject": t.subject,
        "enabled": _trigger_enabled(t.system_key, t) if trig else t.enabled,
        "mandatory": bool(trig and trig.mandatory),
        "deletable": t.kind != "system",
        "updated_at": iso(t.updated_at),
    }
    if trig:
        out |= {"group": trig.group, "when": trig.when, "to": trig.to}
    if full:
        out |= {"preheader": t.preheader, "body_md": t.body_md}
    return out


async def _get_template(session: DbSession, template_id: uuid.UUID) -> EmailTemplate:
    tpl = await session.get(EmailTemplate, template_id)
    if tpl is None:
        raise NotFound("Modelo não encontrado.", code="template_not_found")
    return tpl


async def _campaign_stats(session: DbSession) -> dict[uuid.UUID, dict[str, int]]:
    rows = (
        await session.execute(
            select(
                EmailMessage.campaign_id,
                func.count().filter(EmailMessage.status == "sent"),
                func.count().filter(EmailMessage.status == "failed"),
                func.count().filter(EmailMessage.status == "bounced"),
                func.count().filter(EmailMessage.opened_at.is_not(None)),
                func.count().filter(EmailMessage.clicked_at.is_not(None)),
                func.count().filter(EmailMessage.unsubscribed_at.is_not(None)),
                func.count().filter(EmailMessage.status.in_(("queued", "paused"))),
                func.count(),
            )
            .where(EmailMessage.campaign_id.is_not(None))
            .group_by(EmailMessage.campaign_id)
        )
    ).all()
    keys = ("sent", "failed", "bounced", "opened", "clicked", "unsubscribed", "waiting", "total")
    return {r[0]: dict(zip(keys, map(int, r[1:]), strict=True)) for r in rows}


def _campaign_view(c: EmailCampaign, stats: dict[str, int] | None = None) -> dict[str, Any]:
    s = stats or {}
    sent = s.get("sent", c.sent)
    segment = (c.audience or {}).get("segment", "")
    return {
        "id": str(c.id),
        "name": c.name,
        "kind": c.kind,
        "status": c.status,
        "status_label": CAMPAIGN_LABELS.get(c.status, c.status),
        "template_id": str(c.template_id) if c.template_id else None,
        "subject": c.subject,
        "audience": {"segment": segment, "label": campaigns.AUDIENCES.get(segment, segment)},
        "steps": c.steps or [],
        "recipients": c.recipients if c.kind == "manual" else s.get("total", 0),
        "sent": sent,
        "failed": s.get("failed", c.failed),
        "bounced": s.get("bounced", c.bounced),
        "opened": s.get("opened", c.opened),
        "clicked": s.get("clicked", c.clicked),
        "unsubscribed": s.get("unsubscribed", c.unsubscribed),
        "waiting": s.get("waiting", 0),
        "open_rate": rate(s.get("opened", c.opened), sent),
        "click_rate": rate(s.get("clicked", c.clicked), sent),
        "unsubscribe_rate": rate(s.get("unsubscribed", c.unsubscribed), sent),
        "hourly_cap": c.hourly_cap,
        "scheduled_at": iso(c.scheduled_at),
        "started_at": iso(c.started_at),
        "finished_at": iso(c.finished_at),
        "created_at": iso(c.created_at),
    }


async def _get_campaign(session: DbSession, campaign_id: uuid.UUID) -> EmailCampaign:
    camp = await session.get(EmailCampaign, campaign_id)
    if camp is None:
        raise NotFound("Campanha não encontrada.", code="campaign_not_found")
    return camp


async def _view_one(session: DbSession, camp: EmailCampaign) -> dict[str, Any]:
    await session.flush()
    return _campaign_view(camp, (await _campaign_stats(session)).get(camp.id))


# ------------------------------------------------------------------ overview


@router.get("/overview")
async def overview(admin: AdminUser, session: DbSession) -> dict[str, Any]:
    hourly, daily = await service.caps(session)
    since = datetime.now(UTC) - timedelta(days=30)
    sent_today = await count(
        session,
        select(func.count())
        .select_from(EmailMessage)
        .where(EmailMessage.sent_at >= _today_start()),
    )
    row = (
        await session.execute(
            select(
                func.count().filter(EmailMessage.status == "sent"),
                func.count().filter(EmailMessage.status.in_(("failed", "bounced"))),
                func.count().filter(
                    EmailMessage.status == "sent", EmailMessage.campaign_id.is_(None)
                ),
                func.count().filter(
                    EmailMessage.opened_at.is_not(None), EmailMessage.campaign_id.is_(None)
                ),
                func.count().filter(
                    EmailMessage.status == "sent", EmailMessage.campaign_id.is_not(None)
                ),
                func.count().filter(
                    EmailMessage.opened_at.is_not(None), EmailMessage.campaign_id.is_not(None)
                ),
            ).where(EmailMessage.created_at >= since)
        )
    ).one()
    sent, lost, t_sent, t_open, c_sent, c_open = map(int, row)
    suppressions = await count(session, select(func.count()).select_from(EmailSuppression))
    return {
        "sent_today": sent_today,
        "daily_cap": daily,
        "hourly_cap": hourly,
        "delivery_rate_30d": rate(sent, sent + lost),
        "open_rate_triggers_30d": rate(t_open, t_sent),
        "open_rate_campaigns_30d": rate(c_open, c_sent),
        "suppressions": suppressions,
    }


# ------------------------------------------------------------------ triggers


class TriggerIn(BaseModel):
    enabled: bool


async def _trigger_stats(session: DbSession) -> dict[str, tuple[int, int]]:
    since = datetime.now(UTC) - timedelta(days=30)
    rows = (
        await session.execute(
            select(
                EmailMessage.template_key,
                func.count().filter(EmailMessage.status == "sent"),
                func.count().filter(EmailMessage.opened_at.is_not(None)),
            )
            .where(EmailMessage.campaign_id.is_(None), EmailMessage.created_at >= since)
            .group_by(EmailMessage.template_key)
        )
    ).all()
    return {r[0]: (int(r[1]), int(r[2])) for r in rows}


def _trigger_view(key: str, tpl: EmailTemplate | None, stats: tuple[int, int]) -> dict[str, Any]:
    t = BY_KEY[key]
    sent, opened = stats
    return {
        "key": key,
        "name": t.name,
        "when": t.when,
        "to": t.to,
        "mandatory": t.mandatory,
        "enabled": _trigger_enabled(key, tpl),
        "template_id": str(tpl.id) if tpl else None,
        "sent_30d": sent,
        "open_rate_30d": rate(opened, sent),
    }


async def _templates_by_key(session: DbSession) -> dict[str, EmailTemplate]:
    rows = (
        await session.execute(select(EmailTemplate).where(EmailTemplate.system_key.is_not(None)))
    ).scalars()
    return {t.system_key: t for t in rows if t.system_key}


@router.get("/triggers")
async def triggers(admin: AdminUser, session: DbSession) -> list[dict[str, Any]]:
    tpls = await _templates_by_key(session)
    stats = await _trigger_stats(session)
    return [
        {
            "group": g,
            "items": [
                _trigger_view(t.key, tpls.get(t.key), stats.get(t.key, (0, 0)))
                for t in TRIGGERS
                if t.group == g
            ],
        }
        for g in GROUPS
    ]


@router.post("/triggers/{key}")
async def toggle_trigger(
    key: str, body: TriggerIn, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    trig = BY_KEY.get(key)
    if trig is None:
        raise NotFound("Disparo não encontrado.", code="trigger_not_found")
    if trig.mandatory:
        raise Conflict(
            "E-mail de serviço: este disparo é sempre enviado e não pode ser desligado.",
            code="mandatory_trigger",
        )
    await _ensure_templates(session)
    tpl = await service.template_for(session, key)
    if tpl is None:
        raise NotFound("Modelo do disparo não encontrado.", code="template_not_found")
    tpl.enabled = body.enabled
    tpl.updated_by = admin.id
    await session.flush()
    stats = (await _trigger_stats(session)).get(key, (0, 0))
    return _trigger_view(key, tpl, stats)


# ------------------------------------------------------------------ templates


class TemplateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    subject: str = Field(min_length=1, max_length=200)
    preheader: str = Field(default="", max_length=200)
    body_md: str = Field(default="", max_length=20_000)


class TemplatePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    preheader: str | None = Field(default=None, max_length=200)
    body_md: str | None = Field(default=None, max_length=20_000)
    enabled: bool | None = None


class PreviewIn(BaseModel):
    subject: str = Field(default="", max_length=200)
    preheader: str = Field(default="", max_length=200)
    body_md: str = Field(default="", max_length=20_000)
    system: bool = True


class TestIn(BaseModel):
    to: str | None = None


@router.get("/templates")
async def templates(admin: AdminUser, session: DbSession) -> list[dict[str, Any]]:
    await _ensure_templates(session)
    rows = (
        await session.execute(
            select(EmailTemplate).order_by(EmailTemplate.kind.desc(), EmailTemplate.name)
        )
    ).scalars()
    order = {t.key: i for i, t in enumerate(TRIGGERS)}
    items = [_template_view(t) for t in rows]
    items.sort(
        key=lambda t: (t["kind"] != "system", order.get(t["system_key"] or "", 999), t["name"])
    )
    return items


@router.get("/templates/{template_id}")
async def template(template_id: uuid.UUID, admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return _template_view(await _get_template(session, template_id), full=True)


@router.post("/templates")
async def create_template(body: TemplateIn, admin: AdminUser, session: DbSession) -> dict[str, Any]:
    tpl = EmailTemplate(
        name=body.name.strip(),
        subject=body.subject,
        preheader=body.preheader,
        body_md=body.body_md,
        kind="campaign",
        updated_by=admin.id,
    )
    session.add(tpl)
    await session.flush()
    return _template_view(tpl, full=True)


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: uuid.UUID, body: TemplatePatch, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    tpl = await _get_template(session, template_id)
    data = body.model_dump(exclude_none=True)
    if tpl.kind == "system":
        data.pop("name", None)  # the name follows the trigger
        trig = BY_KEY.get(tpl.system_key or "")
        if "enabled" in data and trig and trig.mandatory and not data["enabled"]:
            raise Conflict(
                "E-mail de serviço: este disparo é sempre enviado e não pode ser desligado.",
                code="mandatory_trigger",
            )
    for k, v in data.items():
        setattr(tpl, k, v.strip() if k == "name" else v)
    tpl.updated_by = admin.id
    await session.flush()
    await session.refresh(tpl)
    return _template_view(tpl, full=True)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> dict[str, bool]:
    tpl = await _get_template(session, template_id)
    if tpl.kind == "system":
        raise Conflict(
            "Modelos do sistema ficam presos a um evento: podem ser editados, nunca apagados.",
            code="system_template",
        )
    await session.delete(tpl)
    return {"ok": True}


@router.post("/preview")
async def preview(body: PreviewIn, admin: AdminUser) -> dict[str, str]:
    msg = _sample_message(body.subject, body.preheader, body.body_md, system=body.system)
    html, text = service.build(msg)
    return {
        "subject": msg.subject,
        "preheader": str(msg.variables.get("_preheader", "")),
        "html": html,
        "text": text,
    }


@router.get("/variables")
async def variables(admin: AdminUser) -> list[dict[str, str]]:
    return [
        {
            "name": name,
            "tag": "{{ " + name + " }}",
            "description": desc,
            "sample": SAMPLE.get(name, ""),
        }
        for name, desc in VARIABLES
    ]


@router.post("/templates/{template_id}/test")
async def test_template(
    template_id: uuid.UUID, body: TestIn, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    tpl = await _get_template(session, template_id)
    to = auth.normalize_email(body.to or admin.email)
    msg = _sample_message(
        tpl.subject, tpl.preheader, tpl.body_md, system=tpl.kind == "system", to=to
    )
    html, text = service.build(msg)
    try:
        delivered = await core_mail.send_mail(
            to=to, subject=f"[Teste] {msg.subject}", text=text, html=html
        )
    except core_mail.MailError as exc:
        raise AppError(f"O servidor de e-mail recusou o envio: {exc}", code="mail_error") from exc
    return {"ok": True, "to": to, "delivered": delivered, "log_only": not delivered}


# ------------------------------------------------------------------ campaigns


class StepIn(BaseModel):
    after_days: int = Field(ge=0, le=365)
    subject: str = Field(default="", max_length=200)
    body_md: str = Field(default="", max_length=20_000)


class CampaignIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    template_id: uuid.UUID | None = None
    audience: str
    kind: str = "manual"
    schedule_at: datetime | None = None
    hourly_cap: int | None = Field(default=None, ge=1, le=100_000)
    subject: str | None = Field(default=None, max_length=200)
    preheader: str | None = Field(default=None, max_length=200)
    body_md: str | None = Field(default=None, max_length=20_000)
    steps: list[StepIn] = Field(default_factory=list)


@router.get("/campaigns")
async def list_campaigns(
    admin: AdminUser, session: DbSession, kind: str | None = None
) -> list[dict[str, Any]]:
    stmt = select(EmailCampaign).order_by(EmailCampaign.created_at.desc())
    if kind:
        stmt = stmt.where(EmailCampaign.kind == kind)
    stats = await _campaign_stats(session)
    return [_campaign_view(c, stats.get(c.id)) for c in (await session.execute(stmt)).scalars()]


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    return await _view_one(session, await _get_campaign(session, campaign_id))


@router.get("/audiences")
async def audiences(admin: AdminUser, session: DbSession) -> list[dict[str, Any]]:
    return [
        {"key": key, "label": label, "size": await campaigns.audience_size(session, key)}
        for key, label in campaigns.AUDIENCES.items()
    ]


@router.post("/campaigns")
async def create_campaign(body: CampaignIn, admin: AdminUser, session: DbSession) -> dict[str, Any]:
    if body.audience not in campaigns.AUDIENCES:
        raise AppError("Público inválido.", code="invalid_audience")
    if body.kind not in ("manual", "auto"):
        raise AppError("Tipo de campanha inválido.", code="invalid_kind")
    tpl = await _get_template(session, body.template_id) if body.template_id else None
    subject = body.subject if body.subject is not None else (tpl.subject if tpl else "")
    preheader = body.preheader if body.preheader is not None else (tpl.preheader if tpl else "")
    body_md = body.body_md if body.body_md is not None else (tpl.body_md if tpl else "")
    steps: list[dict[str, Any]] = []
    if body.kind == "auto":
        if not body.steps:
            raise AppError("Uma sequência precisa de pelo menos um e-mail.", code="steps_required")
        for s in body.steps:
            if not (s.subject or subject) or not (s.body_md or body_md):
                raise AppError(
                    "Cada e-mail da sequência precisa de assunto e texto.", code="step_incomplete"
                )
            steps.append(
                {
                    "after_days": s.after_days,
                    "subject": s.subject or subject,
                    "body_md": s.body_md or body_md,
                }
            )
    elif not subject.strip() or not body_md.strip():
        raise AppError("Escolha um modelo ou escreva assunto e texto.", code="content_required")
    scheduled = body.schedule_at
    if scheduled is not None and scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=SP)
    camp = EmailCampaign(
        name=body.name.strip(),
        template_id=tpl.id if tpl else None,
        subject=subject,
        preheader=preheader,
        body_md=body_md,
        audience={"segment": body.audience},
        kind=body.kind,
        steps=steps,
        status="scheduled" if scheduled and body.kind == "manual" else "draft",
        scheduled_at=scheduled,
        hourly_cap=body.hourly_cap,
        created_by=admin.id,
    )
    session.add(camp)
    return await _view_one(session, camp)


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(
    campaign_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    camp = await _get_campaign(session, campaign_id)
    if camp.kind == "auto":
        if camp.status not in ("draft", "paused"):
            raise Conflict("Esta sequência já está ativa.", code="campaign_state")
        camp.status = "active"
        camp.started_at = camp.started_at or datetime.now(UTC)
    else:
        if camp.status not in ("draft", "scheduled"):
            raise Conflict("Esta campanha já foi iniciada.", code="campaign_state")
        await campaigns.start(session, camp)
    return await _view_one(session, camp)


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    camp = await _get_campaign(session, campaign_id)
    if camp.status not in ("sending", "scheduled", "active"):
        raise Conflict("Só é possível pausar uma campanha em andamento.", code="campaign_state")
    camp.status = "paused"
    await session.execute(
        update(EmailMessage)
        .where(EmailMessage.campaign_id == camp.id, EmailMessage.status == "queued")
        .values(status="paused")
    )
    return await _view_one(session, camp)


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    camp = await _get_campaign(session, campaign_id)
    if camp.status != "paused":
        raise Conflict("A campanha não está pausada.", code="campaign_state")
    if camp.kind == "auto":
        camp.status = "active"
    elif camp.started_at is None:
        camp.status = "scheduled" if camp.scheduled_at else "draft"
    else:
        camp.status = "sending"
        await session.execute(
            update(EmailMessage)
            .where(EmailMessage.campaign_id == camp.id, EmailMessage.status == "paused")
            .values(status="queued")
        )
    return await _view_one(session, camp)


# ------------------------------------------------------------------ messages


def _display_status(m: EmailMessage) -> str:
    if m.unsubscribed_at:
        return "unsubscribed"
    if m.clicked_at:
        return "clicked"
    if m.opened_at:
        return "opened"
    return m.status


@router.get("/messages")
async def messages(
    admin: AdminUser,
    session: DbSession,
    status: str | None = None,
    q: str | None = None,
    campaign_id: uuid.UUID | None = None,
    page: int = 1,
) -> dict[str, Any]:
    per = 100
    stmt = select(EmailMessage, EmailCampaign.name).outerjoin(
        EmailCampaign, EmailCampaign.id == EmailMessage.campaign_id
    )
    where: list[Any] = []
    if status == "opened":
        where.append(EmailMessage.opened_at.is_not(None))
    elif status == "clicked":
        where.append(EmailMessage.clicked_at.is_not(None))
    elif status == "unsubscribed":
        where.append(EmailMessage.unsubscribed_at.is_not(None))
    elif status:
        where.append(EmailMessage.status == status)
    if campaign_id:
        where.append(EmailMessage.campaign_id == campaign_id)
    if q and q.strip():
        term = f"%{q.strip()}%"
        where.append(
            or_(
                EmailMessage.to_email.ilike(term),
                EmailMessage.template_key.ilike(term),
                EmailMessage.subject.ilike(term),
                EmailCampaign.name.ilike(term),
            )
        )
    total = await count(
        session,
        select(func.count())
        .select_from(EmailMessage)
        .outerjoin(EmailCampaign, EmailCampaign.id == EmailMessage.campaign_id)
        .where(*where),
    )
    page = max(page, 1)
    rows = (
        await session.execute(
            stmt.where(*where)
            .order_by(EmailMessage.created_at.desc())
            .offset((page - 1) * per)
            .limit(per)
        )
    ).all()
    items = []
    for m, camp_name in rows:
        st = _display_status(m)
        items.append(
            {
                "id": str(m.id),
                "created_at": iso(m.created_at),
                "sent_at": iso(m.sent_at),
                "to": mask_email(m.to_email),
                "origin_kind": "campaign" if m.campaign_id else "trigger",
                "origin": f"Campanha · {camp_name}" if m.campaign_id else m.template_key,
                "subject": m.subject,
                "status": st,
                "status_label": STATUS_LABELS.get(st, st),
                "error": m.error,
            }
        )
    return {"items": items, "page": page, "per_page": per, "total": total}


# ------------------------------------------------------------------ config


class ConfigIn(BaseModel):
    hourly_cap: int | None = Field(default=None, ge=0, le=100_000)
    daily_cap: int | None = Field(default=None, ge=0, le=1_000_000)
    group_activity: bool | None = None
    warmup_day: int | None = Field(default=None, ge=0, le=30)


async def _config(session: DbSession) -> dict[str, Any]:
    conf = await settings_service.get(session, "mail")
    hourly, daily = await service.caps(session)
    cfg = core_mail.config()
    rows = dict(
        (
            await session.execute(
                select(EmailSuppression.reason, func.count()).group_by(EmailSuppression.reason)
            )
        ).all()
    )
    return {
        "limits": {k: conf[k] for k in ("hourly_cap", "daily_cap", "group_activity", "warmup_day")},
        "effective": {"hourly_cap": hourly, "daily_cap": daily},
        "server": {
            "configured": cfg.configured,
            "provider": cfg.provider or "log",
            "sender": cfg.sender,
            "reply_to": cfg.reply_to,
            "host": cfg.host,
            "port": cfg.port,
            "security": cfg.security,
        },
        "suppressions": [
            {"reason": r, "label": label, "count": int(rows.get(r, 0))}
            for r, label in SUPPRESSION_LABELS.items()
        ],
        "suppressions_total": sum(int(v) for v in rows.values()),
    }


@router.get("/config")
async def get_config(admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await _config(session)


@router.patch("/config")
async def put_config(body: ConfigIn, admin: AdminUser, session: DbSession) -> dict[str, Any]:
    await settings_service.put(
        session, "mail", body.model_dump(exclude_none=True), user_id=admin.id
    )
    return await _config(session)

"""Business events: registration, waitlist, paid events, QR check-in, rating, reminders (§16).

A registration belongs to a person (one per user per event) and to the company. Paid events go
through ``billing.checkout(kind="event")``; the hook confirms the seat (or the waitlist when the
event filled up meanwhile). Canceling a confirmed seat promotes the first person waiting.

"N empresas com alto potencial para você confirmaram presença" counts companies that are the
target of one of the viewer's open recommendations or matches. Only the number is shown: never
who, nor why, nor anything about private purchases (§16).
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Conflict, NotFound
from app.modules.audit.models import AuditLog
from app.modules.auth.deps import Ctx
from app.modules.auth.models import User
from app.modules.billing import service as billing
from app.modules.billing.models import Purchase
from app.modules.billing.service import brl, on_purchase_paid
from app.modules.events.models import Event, EventRegistration
from app.modules.intelligence.engine import blocked_ids
from app.modules.intelligence.models import Recommendation
from app.modules.matches.models import Match
from app.modules.notifications import service as notifications
from app.modules.organizations.models import Organization
from app.modules.organizations.views import iso, org_card

log = logging.getLogger("vip.events")
TZ = ZoneInfo("America/Sao_Paulo")
KIND_LABEL = {"jantar": "Jantar", "rodada": "Rodada", "cafe": "Café", "encontro": "Encontro"}
LIVE_MATCH = ("MATCH_CONFIRMED", "CONNECTION_ACCEPTED", "IN_CONVERSATION", "MUTUAL_INTEREST")


def when_label(dt: datetime) -> str:
    local = dt.astimezone(TZ)
    return local.strftime("%d/%m às %Hh%M").replace("h00", "h")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:80] or "evento"


async def event_counts(session: AsyncSession, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    out: dict[uuid.UUID, dict] = {
        e: {"confirmed": 0, "waitlist": 0, "checked_in": 0, "ratings": 0, "rating_avg": None}
        for e in event_ids
    }
    if not event_ids:
        return out
    rows = await session.execute(
        select(
            EventRegistration.event_id,
            func.count().filter(EventRegistration.status == "confirmed"),
            func.count().filter(EventRegistration.status == "waitlist"),
            func.count().filter(EventRegistration.checked_in_at.is_not(None)),
            func.count(EventRegistration.rating),
            func.avg(EventRegistration.rating),
        )
        .where(EventRegistration.event_id.in_(event_ids))
        .group_by(EventRegistration.event_id)
    )
    for eid, conf, wait, chk, nrat, avg in rows:
        out[eid] = {
            "confirmed": conf,
            "waitlist": wait,
            "checked_in": chk,
            "ratings": nrat,
            "rating_avg": round(float(avg), 1) if avg is not None else None,
        }
    return out


async def high_potential_ids(session: AsyncSession, org_id: uuid.UUID) -> set[uuid.UUID]:
    recs = await session.execute(
        select(Recommendation.target_org_id).where(
            Recommendation.org_id == org_id,
            Recommendation.status.in_(("new", "acted")),
            Recommendation.target_org_id.is_not(None),
        )
    )
    out = {r[0] for r in recs}
    matches = await session.execute(
        select(Match.org_low_id, Match.org_high_id).where(
            or_(Match.org_low_id == org_id, Match.org_high_id == org_id),
            Match.status.in_(LIVE_MATCH),
        )
    )
    for low, high in matches:
        out.add(high if low == org_id else low)
    return out - await blocked_ids(session, org_id) - {org_id}


async def high_potential_confirmed(
    session: AsyncSession, org_id: uuid.UUID, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not event_ids:
        return {}
    wanted = await high_potential_ids(session, org_id)
    out = dict.fromkeys(event_ids, 0)
    if not wanted:
        return out
    rows = await session.execute(
        select(EventRegistration.event_id, func.count(func.distinct(EventRegistration.org_id)))
        .where(
            EventRegistration.event_id.in_(event_ids),
            EventRegistration.status == "confirmed",
            EventRegistration.org_id.in_(wanted),
        )
        .group_by(EventRegistration.event_id)
    )
    for eid, n in rows:
        out[eid] = n
    return out


def reg_view(reg: EventRegistration | None) -> dict[str, Any] | None:
    if reg is None or reg.status == "canceled":
        return None
    return {
        "id": str(reg.id),
        "status": reg.status,
        "checkin_token": reg.checkin_token if reg.status == "confirmed" else None,
        "checked_in_at": iso(reg.checked_in_at),
        "rating": reg.rating,
    }


def event_view(
    ev: Event,
    counts: dict[str, Any],
    *,
    mine: EventRegistration | None = None,
    high_potential: int | None = None,
) -> dict[str, Any]:
    seats_left = max(0, ev.seats - counts["confirmed"])
    out: dict[str, Any] = {
        "id": str(ev.id),
        "slug": ev.slug,
        "title": ev.title,
        "kind": ev.kind,
        "kind_label": KIND_LABEL.get(ev.kind, ev.kind),
        "city": ev.city,
        "state": ev.state,
        "place": ev.place,
        "starts_at": iso(ev.starts_at),
        "ends_at": iso(ev.ends_at),
        "when": when_label(ev.starts_at),
        "seats": ev.seats,
        "seats_taken": counts["confirmed"],
        "seats_left": seats_left,
        "waitlist_open": seats_left == 0,
        "price_cents": ev.price_cents,
        "price": brl(ev.price_cents) if ev.price_cents else "Incluso no plano",
        "image_url": ev.image_url,
        "description": ev.description,
        "status": ev.status,
        "my_registration": reg_view(mine),
    }
    if high_potential is not None:
        out["high_potential_confirmed"] = high_potential
        out["high_potential_label"] = (
            f"{high_potential} empresa{'s' if high_potential != 1 else ''} com alto potencial "
            f"para você confirmar{'am' if high_potential != 1 else 'ou'} presença."
            if high_potential
            else ""
        )
    return out


async def list_upcoming(session: AsyncSession, ctx: Ctx, *, limit: int = 50) -> list[dict]:
    now = datetime.now(UTC)
    events = list(
        (
            await session.execute(
                select(Event)
                .where(
                    Event.status == "published",
                    or_(Event.starts_at >= now, Event.ends_at >= now),
                )
                .order_by(Event.starts_at)
                .limit(limit)
            )
        ).scalars()
    )
    ids = [e.id for e in events]
    counts = await event_counts(session, ids)
    mine = {
        r.event_id: r
        for r in (
            await session.execute(
                select(EventRegistration).where(
                    EventRegistration.event_id.in_(ids), EventRegistration.user_id == ctx.user_id
                )
            )
        ).scalars()
    }
    hp = await high_potential_confirmed(session, ctx.org_id, ids)
    return [
        event_view(e, counts[e.id], mine=mine.get(e.id), high_potential=hp.get(e.id, 0))
        for e in events
    ]


async def _event_for_update(session: AsyncSession, event_id: uuid.UUID) -> Event:
    ev = (
        await session.execute(select(Event).where(Event.id == event_id).with_for_update())
    ).scalar_one_or_none()
    if ev is None:
        raise NotFound("Evento não encontrado.", code="event_not_found")
    return ev


async def _confirmed(session: AsyncSession, event_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count()).where(
                EventRegistration.event_id == event_id, EventRegistration.status == "confirmed"
            )
        )
    ).scalar_one()


async def _my_reg(
    session: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID
) -> EventRegistration | None:
    return (
        await session.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id, EventRegistration.user_id == user_id
            )
        )
    ).scalar_one_or_none()


def _vars(ev: Event) -> dict[str, str]:
    return {
        "evento": ev.title,
        "data_evento": when_label(ev.starts_at),
        "local": f"{ev.place}, {ev.city}".strip(", "),
    }


async def _place(
    session: AsyncSession, ev: Event, org_id: uuid.UUID, user: User
) -> EventRegistration:
    """Create or revive the person's registration: confirmed when there is a seat, else waitlist."""
    reg = await _my_reg(session, ev.id, user.id)
    status = "confirmed" if await _confirmed(session, ev.id) < ev.seats else "waitlist"
    if reg is None:
        reg = EventRegistration(
            event_id=ev.id,
            org_id=org_id,
            user_id=user.id,
            status=status,
            checkin_token=secrets.token_urlsafe(24),
        )
        session.add(reg)
    else:
        reg.status = status
        reg.org_id = org_id
        reg.checked_in_at = None
        reg.checkin_token = secrets.token_urlsafe(24)
    await session.flush()
    if status == "confirmed":
        await notifications.notify(
            session,
            org_id,
            kind="event.registered",
            title=f"Inscrição confirmada: {ev.title}",
            link="/app/eventos",
            users=[user],
            email_vars=_vars(ev),
        )
    return reg


async def register(session: AsyncSession, ctx: Ctx, event_id: uuid.UUID) -> dict[str, Any]:
    ev = await _event_for_update(session, event_id)
    if ev.status != "published":
        raise Conflict("Este evento não está aberto para inscrições.", code="event_closed")
    if ev.starts_at <= datetime.now(UTC):
        raise Conflict("Este evento já começou.", code="event_started")
    reg = await _my_reg(session, ev.id, ctx.user_id)
    if reg is not None and reg.status in ("confirmed", "waitlist"):
        raise Conflict("Você já está inscrito neste evento.", code="already_registered")
    if ev.price_cents:
        checkout = await billing.checkout(
            session,
            ctx.org,
            ctx.user,
            kind="event",
            ref=str(ev.id),
            name=ev.title,
            amount_cents=ev.price_cents,
            return_path="/app/eventos",
            data={"event_id": str(ev.id), "user_id": str(ctx.user_id)},
        )
        reg = await _my_reg(session, ev.id, ctx.user_id)
        return {"checkout": checkout, "registration": reg_view(reg)}
    reg = await _place(session, ev, ctx.org_id, ctx.user)
    return {"checkout": None, "registration": reg_view(reg)}


@on_purchase_paid("event")
async def _event_paid(session: AsyncSession, purchase: Purchase) -> None:
    data = purchase.data or {}
    ev = await session.get(Event, uuid.UUID(str(data.get("event_id") or purchase.ref)))
    user = await session.get(User, uuid.UUID(str(data["user_id"]))) if data.get("user_id") else None
    if ev is None or user is None:
        log.warning("paid event purchase %s without event/user", purchase.id)
        return
    ev = await _event_for_update(session, ev.id)
    await _place(session, ev, purchase.org_id, user)


async def promote(session: AsyncSession, ev: Event) -> list[EventRegistration]:
    """Fill free seats with the people waiting, in order of arrival."""
    promoted = []
    free = ev.seats - await _confirmed(session, ev.id)
    if free <= 0:
        return promoted
    waiting = (
        await session.execute(
            select(EventRegistration)
            .where(EventRegistration.event_id == ev.id, EventRegistration.status == "waitlist")
            .order_by(EventRegistration.created_at)
            .limit(free)
        )
    ).scalars()
    for reg in waiting:
        reg.status = "confirmed"
        promoted.append(reg)
        user = await session.get(User, reg.user_id)
        await notifications.notify(
            session,
            reg.org_id,
            kind="event.waitlist_open",
            title=f"Abriu uma vaga: {ev.title}",
            link="/app/eventos",
            users=[user] if user else [],
            email_vars=_vars(ev),
        )
    await session.flush()
    return promoted


async def cancel(session: AsyncSession, ctx: Ctx, event_id: uuid.UUID) -> None:
    ev = await _event_for_update(session, event_id)
    reg = await _my_reg(session, ev.id, ctx.user_id)
    if reg is None or reg.status == "canceled":
        raise NotFound("Você não está inscrito neste evento.", code="not_registered")
    was_confirmed = reg.status == "confirmed"
    reg.status = "canceled"
    await session.flush()
    if was_confirmed:
        await promote(session, ev)


async def rate(session: AsyncSession, ctx: Ctx, event_id: uuid.UUID, rating: int) -> None:
    ev = await session.get(Event, event_id)
    if ev is None:
        raise NotFound("Evento não encontrado.", code="event_not_found")
    reg = await _my_reg(session, ev.id, ctx.user_id)
    if reg is None or reg.status != "confirmed":
        raise Conflict("Só quem participou pode avaliar.", code="not_attendee")
    if ev.starts_at > datetime.now(UTC):
        raise Conflict("A avaliação abre depois do evento.", code="event_not_started")
    if not 1 <= rating <= 5:
        raise AppError("Dê uma nota de 1 a 5.", code="invalid_rating")
    reg.rating = rating
    await session.flush()


# ------------------------------------------------------------------ team panel


async def admin_list(session: AsyncSession) -> list[dict[str, Any]]:
    events = list(
        (await session.execute(select(Event).order_by(Event.starts_at.desc()).limit(200))).scalars()
    )
    counts = await event_counts(session, [e.id for e in events])
    out = []
    for e in events:
        c = counts[e.id]
        out.append(
            {
                **event_view(e, c),
                "waitlist": c["waitlist"],
                "checked_in": c["checked_in"],
                "checkin_pct": round(c["checked_in"] * 100 / c["confirmed"])
                if c["confirmed"]
                else None,
                "ratings": c["ratings"],
                "rating_avg": c["rating_avg"],
            }
        )
    return out


async def create_event(session: AsyncSession, values: dict[str, Any]) -> Event:
    base = slugify(values["title"])
    ev = Event(slug=f"{base}-{secrets.token_hex(3)}", **values)
    session.add(ev)
    await session.flush()
    return ev


async def update_event(session: AsyncSession, event_id: uuid.UUID, values: dict[str, Any]) -> Event:
    ev = await _event_for_update(session, event_id)
    for k, v in values.items():
        setattr(ev, k, v)
    await session.flush()
    if ev.status == "published":
        await promote(session, ev)  # more seats → people waiting get in
    return ev


async def admin_registrations(session: AsyncSession, event_id: uuid.UUID) -> list[dict[str, Any]]:
    if await session.get(Event, event_id) is None:
        raise NotFound("Evento não encontrado.", code="event_not_found")
    rows = (
        await session.execute(
            select(EventRegistration, Organization, User)
            .join(Organization, Organization.id == EventRegistration.org_id)
            .join(User, User.id == EventRegistration.user_id)
            .where(EventRegistration.event_id == event_id)
            .order_by(EventRegistration.created_at)
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "org": org_card(o),
            "person": {"name": u.full_name, "job_title": u.job_title, "email": u.email},
            "checked_in_at": iso(r.checked_in_at),
            "rating": r.rating,
            "created_at": iso(r.created_at),
        }
        for r, o, u in rows
    ]


async def checkin(session: AsyncSession, token: str) -> dict[str, Any]:
    reg = (
        await session.execute(
            select(EventRegistration).where(EventRegistration.checkin_token == token)
        )
    ).scalar_one_or_none()
    if reg is None:
        raise NotFound("QR Code não reconhecido.", code="checkin_not_found")
    if reg.status != "confirmed":
        raise Conflict("Esta inscrição não está confirmada.", code="checkin_not_confirmed")
    already = reg.checked_in_at is not None
    if not already:
        reg.checked_in_at = datetime.now(UTC)
    org = await session.get(Organization, reg.org_id)
    user = await session.get(User, reg.user_id)
    ev = await session.get(Event, reg.event_id)
    await session.flush()
    return {
        "already": already,
        "checked_in_at": iso(reg.checked_in_at),
        "event": {"id": str(ev.id), "title": ev.title} if ev else None,
        "org": org_card(org) if org else None,
        "person": {"name": user.full_name, "job_title": user.job_title} if user else None,
    }


# ------------------------------------------------------------------ background


async def tick(session: AsyncSession) -> int:
    """``event.reminder`` once per confirmed registration, ~24 h before the event."""
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(EventRegistration, Event)
            .join(Event, Event.id == EventRegistration.event_id)
            .where(
                Event.status == "published",
                Event.starts_at > now,
                Event.starts_at <= now + timedelta(hours=24),
                EventRegistration.status == "confirmed",
            )
        )
    ).all()
    sent = 0
    for reg, ev in rows:
        key = f"{reg.id}"
        done = (
            await session.execute(
                select(AuditLog.id).where(
                    AuditLog.action == "event.reminder", AuditLog.target_id == key
                )
            )
        ).first()
        if done:
            continue
        session.add(
            AuditLog(org_id=reg.org_id, action="event.reminder", target_type="event", target_id=key)
        )
        user = await session.get(User, reg.user_id)
        if user is None:
            continue
        await notifications.notify(
            session,
            reg.org_id,
            kind="event.reminder",
            title=f"Amanhã: {ev.title}",
            link="/app/eventos",
            users=[user],
            email_vars=_vars(ev),
        )
        sent += 1
    await session.flush()
    return sent


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
            log.exception("events tick failed")
        await asyncio.sleep(600)

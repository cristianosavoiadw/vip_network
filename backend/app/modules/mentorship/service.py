"""Executive mentorship (scope §2.3, §17). Confidential and segregated: nothing here is read by
discovery, matching or recommendations, and the team panel sees only the agenda (date, mentor,
mentee company, topic), never diagnosis, plan, goals or documents."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.modules.auth.deps import Ctx
from app.modules.billing import service as billing
from app.modules.billing.models import Purchase
from app.modules.billing.service import add_months, brl, on_purchase_paid
from app.modules.events.service import when_label
from app.modules.mentorship.models import (
    Mentor,
    MentorshipDocument,
    MentorshipPlan,
    MentorshipSession,
)
from app.modules.notifications import service as notifications
from app.modules.organizations.models import Organization
from app.modules.organizations.views import iso, org_card

PRICE_CENTS = 1_500_000
PROGRAM = {
    "name": "Mentoria VIP Network",
    "price_cents": PRICE_CENTS,
    "price": brl(PRICE_CENTS),
    "period": "ano",
    "months": 12,
    "includes": [
        "Diagnóstico do negócio",
        "Plano estratégico com metas",
        "Sessões individuais (quantidade definida no programa)",
        "Acompanhamento de resultados",
        "Assistente de apoio entre sessões",
    ],
    "note": "Os dados da mentoria ficam separados do resto da plataforma e não são usados para "
    "recomendar empresas.",
}
OPEN_SESSION = ("requested", "scheduled", "done")


def mentor_view(m: Mentor) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "name": m.name,
        "headline": m.headline,
        "bio": m.bio,
        "photo_url": m.photo_url,
        "is_lead": m.is_lead,
        "active": m.active,
    }


def session_view(s: MentorshipSession) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "starts_at": iso(s.starts_at),
        "topic": s.topic,
        "status": s.status,
    }


async def mentors(session: AsyncSession, *, only_active: bool = True) -> list[Mentor]:
    q = select(Mentor).order_by(Mentor.is_lead.desc(), Mentor.name)
    if only_active:
        q = q.where(Mentor.active.is_(True))
    return list((await session.execute(q)).scalars())


async def current_plan(session: AsyncSession, org_id: uuid.UUID) -> MentorshipPlan | None:
    plans = list(
        (
            await session.execute(
                select(MentorshipPlan)
                .where(MentorshipPlan.org_id == org_id, MentorshipPlan.status != "canceled")
                .order_by(MentorshipPlan.created_at.desc())
            )
        ).scalars()
    )
    return next((p for p in plans if p.status == "active"), None) or next(
        (p for p in plans if p.status != "pending"), None
    )


async def _used(session: AsyncSession, plan_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count()).where(
                MentorshipSession.plan_id == plan_id, MentorshipSession.status.in_(OPEN_SESSION)
            )
        )
    ).scalar_one()


async def overview(session: AsyncSession, ctx: Ctx) -> dict[str, Any]:
    plan = await current_plan(session, ctx.org_id)
    out: dict[str, Any] = {
        "program": PROGRAM,
        "mentors": [mentor_view(m) for m in await mentors(session)],
        "plan": None,
    }
    if plan is None:
        return out
    sessions = list(
        (
            await session.execute(
                select(MentorshipSession)
                .where(MentorshipSession.plan_id == plan.id)
                .order_by(MentorshipSession.starts_at)
            )
        ).scalars()
    )
    docs = list(
        (
            await session.execute(
                select(MentorshipDocument)
                .where(MentorshipDocument.plan_id == plan.id)
                .order_by(MentorshipDocument.created_at)
            )
        ).scalars()
    )
    mentor = await session.get(Mentor, plan.mentor_id) if plan.mentor_id else None
    out["plan"] = {
        "id": str(plan.id),
        "status": plan.status,
        "starts_on": plan.starts_on.isoformat() if plan.starts_on else None,
        "ends_on": plan.ends_on.isoformat() if plan.ends_on else None,
        "sessions_total": plan.sessions_total,
        "sessions_used": sum(1 for s in sessions if s.status in OPEN_SESSION),
        "mentor": mentor_view(mentor) if mentor else None,
        "diagnosis": plan.diagnosis,
        "strategic_plan": plan.strategic_plan,
        "goals": plan.goals,
        "sessions": [session_view(s) for s in sessions],
        "documents": [
            {"id": str(d.id), "name": d.name, "url": d.url, "created_at": iso(d.created_at)}
            for d in docs
        ],
    }
    return out


async def checkout(session: AsyncSession, ctx: Ctx) -> dict[str, Any]:
    active = await current_plan(session, ctx.org_id)
    if active is not None and active.status == "active":
        raise Conflict("Sua empresa já participa da mentoria.", code="mentorship_active")
    lead = next(iter(await mentors(session)), None)
    plan = MentorshipPlan(
        org_id=ctx.org_id,
        mentor_id=lead.id if lead else None,
        status="pending",
        price_cents=PRICE_CENTS,
    )
    session.add(plan)
    await session.flush()
    return await billing.checkout(
        session,
        ctx.org,
        ctx.user,
        kind="mentorship",
        ref=str(plan.id),
        name="Mentoria VIP Network (anual)",
        amount_cents=PRICE_CENTS,
        return_path="/app/mentoria",
        data={"plan_id": str(plan.id)},
    )


@on_purchase_paid("mentorship")
async def _mentorship_paid(session: AsyncSession, purchase: Purchase) -> None:
    plan_id = (purchase.data or {}).get("plan_id") or purchase.ref
    plan = await session.get(MentorshipPlan, uuid.UUID(str(plan_id))) if plan_id else None
    if plan is None or plan.org_id != purchase.org_id:
        plan = MentorshipPlan(org_id=purchase.org_id, price_cents=purchase.amount_cents)
        session.add(plan)
    today = datetime.now(UTC).date()
    plan.status = "active"
    plan.starts_on = today
    plan.ends_on = add_months(datetime.now(UTC), 12).date()
    await session.flush()
    await notifications.notify(
        session,
        purchase.org_id,
        kind="mentorship.purchased",
        title="Bem-vindo à Mentoria VIP Network",
        link="/app/mentoria",
        departments=("diretoria",),
    )


async def request_session(
    session: AsyncSession, ctx: Ctx, starts_at: datetime, topic: str
) -> MentorshipSession:
    plan = await current_plan(session, ctx.org_id)
    if plan is None or plan.status != "active":
        raise Conflict("A agenda abre depois da contratação da mentoria.", code="no_mentorship")
    if starts_at <= datetime.now(UTC):
        raise Conflict("Escolha uma data futura.", code="past_date")
    if await _used(session, plan.id) >= plan.sessions_total:
        raise Conflict("Todas as sessões do programa já foram usadas.", code="sessions_used")
    s = MentorshipSession(plan_id=plan.id, starts_at=starts_at, topic=topic, status="requested")
    session.add(s)
    await session.flush()
    return s


# ------------------------------------------------------------------ team panel (no content)


async def admin_summary(session: AsyncSession) -> dict[str, Any]:
    today = datetime.now(UTC).date()
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    active = list(
        (
            await session.execute(select(MentorshipPlan).where(MentorshipPlan.status == "active"))
        ).scalars()
    )
    sessions_month = (
        await session.execute(
            select(func.count()).where(
                MentorshipSession.starts_at >= month_start,
                MentorshipSession.starts_at < add_months(month_start, 1),
                MentorshipSession.status != "canceled",
            )
        )
    ).scalar_one()
    ms = await mentors(session)
    return {
        "active_mentees": len(active),
        "annual_revenue_cents": sum(p.price_cents for p in active),
        "mentors": len(ms),
        "sessions_month": sessions_month,
        "renewals_60d": sum(
            1 for p in active if p.ends_on and today <= p.ends_on <= today + timedelta(days=60)
        ),
    }


async def admin_plans(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(MentorshipPlan, Organization)
            .join(Organization, Organization.id == MentorshipPlan.org_id)
            .where(MentorshipPlan.status != "pending")
            .order_by(MentorshipPlan.created_at.desc())
        )
    ).all()
    names = {m.id: m.name for m in await mentors(session, only_active=False)}
    out = []
    for plan, org in rows:
        out.append(
            {
                "id": str(plan.id),
                "org": org_card(org),
                "status": plan.status,
                "mentor": names.get(plan.mentor_id) if plan.mentor_id else None,
                "mentor_id": str(plan.mentor_id) if plan.mentor_id else None,
                "starts_on": plan.starts_on.isoformat() if plan.starts_on else None,
                "ends_on": plan.ends_on.isoformat() if plan.ends_on else None,
                "sessions_total": plan.sessions_total,
                "sessions_used": await _used(session, plan.id),
                "price_cents": plan.price_cents,
            }
        )
    return out


async def update_plan(
    session: AsyncSession, plan_id: uuid.UUID, values: dict[str, Any]
) -> MentorshipPlan:
    plan = await session.get(MentorshipPlan, plan_id)
    if plan is None:
        raise NotFound("Plano não encontrado.", code="plan_not_found")
    for k, v in values.items():
        setattr(plan, k, v)
    await session.flush()
    return plan


async def agenda(session: AsyncSession, *, since: date | None = None) -> list[dict[str, Any]]:
    start = datetime.combine(since or datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
    rows = (
        await session.execute(
            select(MentorshipSession, MentorshipPlan, Organization)
            .join(MentorshipPlan, MentorshipPlan.id == MentorshipSession.plan_id)
            .join(Organization, Organization.id == MentorshipPlan.org_id)
            .where(MentorshipSession.starts_at >= start)
            .order_by(MentorshipSession.starts_at)
            .limit(300)
        )
    ).all()
    names = {m.id: m.name for m in await mentors(session, only_active=False)}
    return [
        {
            "id": str(s.id),
            "plan_id": str(p.id),
            "starts_at": iso(s.starts_at),
            "mentor": names.get(p.mentor_id) if p.mentor_id else None,
            "mentee": o.display_name,
            "topic": s.topic,
            "status": s.status,
        }
        for s, p, o in rows
    ]


async def _notify_session(session: AsyncSession, plan: MentorshipPlan, s: MentorshipSession):  # noqa: ANN202
    await notifications.notify(
        session,
        plan.org_id,
        kind="mentorship.session",
        title=f"Sessão de mentoria: {when_label(s.starts_at)}",
        link="/app/mentoria",
        departments=("diretoria",),
        email_vars={"data_sessao": when_label(s.starts_at), "tema": s.topic},
    )


async def schedule(
    session: AsyncSession, plan_id: uuid.UUID, starts_at: datetime, topic: str
) -> MentorshipSession:
    plan = await session.get(MentorshipPlan, plan_id)
    if plan is None or plan.status != "active":
        raise NotFound("Plano ativo não encontrado.", code="plan_not_found")
    s = MentorshipSession(plan_id=plan.id, starts_at=starts_at, topic=topic, status="scheduled")
    session.add(s)
    await session.flush()
    await _notify_session(session, plan, s)
    return s


async def update_session(
    session: AsyncSession, session_id: uuid.UUID, values: dict[str, Any]
) -> MentorshipSession:
    s = await session.get(MentorshipSession, session_id)
    if s is None:
        raise NotFound("Sessão não encontrada.", code="session_not_found")
    for k, v in values.items():
        setattr(s, k, v)
    await session.flush()
    plan = await session.get(MentorshipPlan, s.plan_id)
    if plan is not None and ({"starts_at", "status", "topic"} & values.keys()):
        await _notify_session(session, plan, s)
    return s

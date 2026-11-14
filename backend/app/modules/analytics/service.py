"""Team-panel analytics (scope §26 Analytics, §30): MRR, ARR, churn, LTV, revenue by source,
acquisition funnel, retention cohorts and the main indicator.

The subscription math lives here and is reused by ``admin/service.py`` (Visão geral,
Assinaturas). Calendar boundaries ("today", "this month") follow America/Sao_Paulo.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import PRICES_CENTS, Invoice, Purchase, Subscription
from app.modules.billing.service import add_months
from app.modules.invites.models import Invite
from app.modules.opportunities.models import Opportunity
from app.modules.organizations.models import Organization

SP = ZoneInfo("America/Sao_Paulo")
MONTHS_PT = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
# stages that count for the main indicator (§30): effective negotiation or confirmed deal
QUALIFIED_STAGES = ("negotiation", "proposal", "won")
COHORT_MONTHS = (1, 2, 3, 6)
SOURCES = (
    ("subscriptions", "Assinaturas"),
    ("boost", "Brilhar"),
    ("mentorship", "Mentoria"),
    ("event", "Eventos"),
)


# ------------------------------------------------------------------ time helpers


def now() -> datetime:
    return datetime.now(UTC)


def day_start(ref: datetime) -> datetime:
    local = ref.astimezone(SP)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def month_start(ref: datetime, offset: int = 0) -> datetime:
    local = ref.astimezone(SP).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if offset:
        local = add_months(local, offset)
    return local.astimezone(UTC)


def month_label(ref: datetime) -> str:
    local = ref.astimezone(SP)
    return f"{MONTHS_PT[local.month - 1]}/{local.year}"


def rate(part: int | float, whole: int | float) -> float | None:
    """A fraction 0..1 rounded to 4 places, None when there is nothing to divide."""
    return round(part / whole, 4) if whole else None


async def count(session: AsyncSession, stmt: Any) -> int:
    return int((await session.execute(stmt)).scalar_one() or 0)


# ------------------------------------------------------------------ subscription math


def is_paying(sub: Subscription, at: datetime | None = None) -> bool:
    """Counts in MRR: an active charged subscription. Trials and the VIP free period are out;
    a VIP that moved to ``then_charge`` after ``vip_until`` counts like a standard one."""
    at = at or now()
    if sub.status != "active":
        return False
    return not (sub.kind == "vip" and sub.vip_until is not None and sub.vip_until > at)


def monthly_value_cents(sub: Subscription) -> float:
    return PRICES_CENTS["annual"] / 12 if sub.plan == "annual" else float(PRICES_CENTS["monthly"])


def mrr_cents(subs: Iterable[Subscription], at: datetime | None = None) -> int:
    """active standard monthly × R$ 250 + annual × R$ 2.500 / 12 (trials and VIP excluded)."""
    at = at or now()
    return round(sum(monthly_value_cents(s) for s in subs if is_paying(s, at)))


def in_vip_period(sub: Subscription, at: datetime) -> bool:
    return (
        sub.kind == "vip"
        and sub.vip_until is not None
        and sub.vip_until > at
        and sub.status != "canceled"
    )


def trial_conversion(subs: Iterable[Subscription], at: datetime, days: int = 90) -> dict[str, Any]:
    """Standard trials that ended in the window and became paying (or paid then canceled)."""
    since = at - timedelta(days=days)
    ended = [
        s
        for s in subs
        if s.kind == "standard"
        and s.trial_start is not None
        and s.trial_end is not None
        and since <= s.trial_end <= at
    ]
    converted = [
        s
        for s in ended
        if s.status in ("active", "past_due")
        or (s.status == "canceled" and s.canceled_at is not None and s.canceled_at > s.trial_end)
    ]
    return {
        "ended": len(ended),
        "converted": len(converted),
        "rate": rate(len(converted), len(ended)),
        "days": days,
    }


def churn(subs: Iterable[Subscription], since: datetime, at: datetime | None = None) -> dict:
    """Paying subscriptions canceled since ``since`` over (paying now + those canceled).
    A cancellation during the trial or the VIP free period is not churn."""
    at = at or now()
    subs = list(subs)
    canceled = [
        s
        for s in subs
        if s.status == "canceled"
        and s.canceled_at is not None
        and s.canceled_at >= since
        and not (s.trial_end is not None and s.canceled_at <= s.trial_end)
        and not (s.kind == "vip" and s.vip_until is not None and s.canceled_at <= s.vip_until)
    ]
    base = sum(1 for s in subs if is_paying(s, at)) + len(canceled)
    return {"canceled": len(canceled), "base": base, "rate": rate(len(canceled), base)}


async def all_subscriptions(session: AsyncSession) -> list[Subscription]:
    return list((await session.execute(select(Subscription))).scalars())


# ------------------------------------------------------------------ main indicator


def reached_qualified_at(opp: Opportunity) -> datetime | None:
    """When the opportunity first reached negotiation/proposal/won (stage history written by
    opportunities/service.py: {"action": "stage", "to": ..., "at": iso})."""
    for h in opp.history or []:
        if not isinstance(h, dict) or h.get("action") != "stage":
            continue
        if h.get("to") in QUALIFIED_STAGES and h.get("at"):
            try:
                at = datetime.fromisoformat(str(h["at"]))
            except ValueError:
                continue
            return at if at.tzinfo else at.replace(tzinfo=UTC)
    if opp.stage in QUALIFIED_STAGES:
        return opp.updated_at
    return None


async def main_indicator(session: AsyncSession, at: datetime) -> dict[str, Any]:
    m0, prev = month_start(at), month_start(at, -1)
    rows = (
        (await session.execute(select(Opportunity).where(Opportunity.updated_at >= prev)))
        .scalars()
        .all()
    )
    this_month = last_month = 0
    for opp in rows:
        when = reached_qualified_at(opp)
        if when is None:
            continue
        if when >= m0:
            this_month += 1
        elif when >= prev:
            last_month += 1
    change = round((this_month - last_month) / last_month, 4) if last_month else None
    return {
        "label": "Oportunidades qualificadas que viraram negociação ou negócio confirmado",
        "this_month": this_month,
        "last_month": last_month,
        "change": change,
        "month": month_label(at),
        "previous_month": month_label(prev),
    }


# ------------------------------------------------------------------ analytics page


async def _revenue(session: AsyncSession, since: datetime) -> list[dict[str, Any]]:
    subs_cents = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(Invoice.amount_cents), 0)).where(
                    Invoice.status == "paid", Invoice.paid_at >= since
                )
            )
        ).scalar_one()
    )
    by_kind = dict(
        (
            await session.execute(
                select(Purchase.kind, func.coalesce(func.sum(Purchase.amount_cents), 0))
                .where(Purchase.status == "paid", Purchase.paid_at >= since)
                .group_by(Purchase.kind)
            )
        ).all()
    )
    values = {"subscriptions": subs_cents, **{k: int(v) for k, v in by_kind.items()}}
    total = sum(values.get(k, 0) for k, _ in SOURCES)
    return [
        {
            "key": key,
            "label": label,
            "cents": values.get(key, 0),
            "share": rate(values.get(key, 0), total),
        }
        for key, label in SOURCES
    ]


async def _funnel(session: AsyncSession, at: datetime, subs: list[Subscription]) -> list[dict]:
    since = at - timedelta(days=30)
    created = await count(
        session,
        select(func.count()).select_from(Organization).where(Organization.created_at >= since),
    )
    finished = await count(
        session,
        select(func.count())
        .select_from(Organization)
        .where(Organization.onboarding_completed_at >= since),
    )
    trials = sum(
        1
        for s in subs
        if s.kind == "standard"
        and s.trial_start is not None
        and s.trial_end is not None
        and s.trial_start >= since
    )
    accepted = await count(
        session, select(func.count()).select_from(Invite).where(Invite.accepted_at >= since)
    )
    conv = trial_conversion(subs, at, 30)
    return [
        {"key": "orgs_created", "label": "Cadastros iniciados", "count": created, "rate": None},
        {
            "key": "onboarding_finished",
            "label": "Cadastros concluídos",
            "count": finished,
            "rate": rate(finished, created),
        },
        {
            "key": "trials_started",
            "label": "Testes iniciados",
            "count": trials,
            "rate": rate(trials, finished),
        },
        {"key": "invites_accepted", "label": "Convites aceitos", "count": accepted, "rate": None},
        {
            "key": "trial_to_paid",
            "label": "Teste → pagante",
            "count": conv["converted"],
            "rate": conv["rate"],
        },
    ]


async def _cohorts(session: AsyncSession, at: datetime, months: int = 6) -> list[dict[str, Any]]:
    first = month_start(at, -(months - 1))
    entry = func.coalesce(Organization.onboarding_completed_at, Organization.created_at)
    rows = (
        await session.execute(
            select(Organization, Subscription, entry)
            .outerjoin(Subscription, Subscription.org_id == Organization.id)
            .where(Organization.status != "pending", entry >= first)
        )
    ).all()
    out: list[dict[str, Any]] = []
    for i in range(months):
        start, end = month_start(at, -(months - 1) + i), month_start(at, -(months - 2) + i)
        cohort = [(org, sub) for org, sub, when in rows if start <= when < end]
        cells: dict[str, float | None] = {}
        for k in COHORT_MONTHS:
            checkpoint = add_months(start.astimezone(SP), k).astimezone(UTC)
            if checkpoint > at or not cohort:
                cells[str(k)] = None
                continue
            kept = sum(
                1
                for org, sub in cohort
                if sub is not None
                and org.status != "suspended"
                and not (sub.canceled_at is not None and sub.canceled_at <= checkpoint)
            )
            cells[str(k)] = rate(kept, len(cohort))
        out.append({"month": month_label(start), "orgs": len(cohort), "retention": cells})
    return out


async def analytics(session: AsyncSession) -> dict[str, Any]:
    at = now()
    m0 = month_start(at)
    subs = await all_subscriptions(session)
    mrr = mrr_cents(subs, at)
    paying = sum(1 for s in subs if is_paying(s, at))
    ch = churn(subs, m0, at)
    arpa = mrr / paying if paying else 0
    # LTV = ARPA / monthly churn, capped at 60 months when churn is (still) zero
    ltv = round(arpa / max(ch["rate"] or 0, 1 / 60)) if paying else 0
    return {
        "mrr_cents": mrr,
        "arr_cents": mrr * 12,
        "paying": paying,
        "churn": ch,
        "arpa_cents": round(arpa),
        "ltv_cents": ltv,
        "revenue_month": await _revenue(session, m0),
        "revenue_note": "Mentoria é contrato anual e fica fora do MRR.",
        "funnel_30d": await _funnel(session, at, subs),
        "cohorts": await _cohorts(session, at),
        "main_indicator": await main_indicator(session, at),
    }

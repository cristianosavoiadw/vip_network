"""Brilhar na Rede (scope §2.2): packages, checkout, campaigns and their numbers.

A campaign starts when paid, or right after the company's current campaign ends (stacked).
Numbers come from ``OrgDayStat``: impressions during the campaign vs the organic baseline of
the same number of days before it. The copy never promises results; the boost only changes the
position in sponsored slots, never the computed compatibility.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.auth.deps import Ctx
from app.modules.billing import service as billing
from app.modules.billing.models import Purchase
from app.modules.billing.service import brl, on_purchase_paid
from app.modules.boosts.models import PACKAGES, BoostCampaign, OrgDayStat
from app.modules.notifications import service as notifications
from app.modules.organizations.models import Organization
from app.modules.organizations.views import iso, org_card

log = logging.getLogger("vip.boosts")
TZ = ZoneInfo("America/Sao_Paulo")
DISCLAIMER = (
    "O destaque aumenta a exposição nas áreas patrocinadas, mas não altera a compatibilidade "
    "calculada nem garante visualizações, contatos ou vendas."
)
AUDIENCE = ("diretoria", "comercial")


def package_label(days: int) -> str:
    return f"{days} dia{'s' if days != 1 else ''}"


def packages() -> list[dict[str, Any]]:
    return [
        {"days": d, "label": package_label(d), "price_cents": p, "price": brl(p)}
        for d, p in sorted(PACKAGES.items())
    ]


def _fmt(dt: datetime | None) -> str:
    return dt.astimezone(TZ).strftime("%d/%m/%Y") if dt else ""


async def checkout(session: AsyncSession, ctx: Ctx, days: int) -> dict[str, Any]:
    if days not in PACKAGES:
        raise AppError("Pacote inválido. Escolha 1, 10 ou 30 dias.", code="invalid_package")
    return await billing.checkout(
        session,
        ctx.org,
        ctx.user,
        kind="boost",
        ref=str(days),
        name=f"Brilhar na Rede · {package_label(days)}",
        amount_cents=PACKAGES[days],
        return_path="/app/assinatura",
        data={"days": days},
    )


async def _last_end(session: AsyncSession, org_id: uuid.UUID) -> datetime | None:
    return (
        await session.execute(
            select(func.max(BoostCampaign.ends_at)).where(
                BoostCampaign.org_id == org_id, BoostCampaign.status == "active"
            )
        )
    ).scalar_one()


@on_purchase_paid("boost")
async def activate(session: AsyncSession, purchase: Purchase) -> BoostCampaign:
    days = int((purchase.data or {}).get("days") or purchase.ref)
    now = datetime.now(UTC)
    last = await _last_end(session, purchase.org_id)
    start = last if last and last > now else now
    camp = BoostCampaign(
        org_id=purchase.org_id,
        purchase_id=purchase.id,
        days=days,
        amount_cents=purchase.amount_cents,
        starts_at=start,
        ends_at=start + timedelta(days=days),
        status="active",
    )
    session.add(camp)
    await session.flush()
    await notifications.notify(
        session,
        purchase.org_id,
        kind="boost.purchased",
        title=f"Sua empresa está em destaque por {package_label(days)}",
        link="/app/assinatura",
        departments=AUDIENCE,
        email_vars={"dias": str(days), "inicio": _fmt(start), "fim": _fmt(camp.ends_at)},
    )
    return camp


def _day(dt: datetime) -> date:
    return dt.astimezone(TZ).date()


async def stats_between(
    session: AsyncSession, org_id: uuid.UUID, first: date, last: date
) -> dict[str, int]:
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(OrgDayStat.impressions), 0),
                func.coalesce(func.sum(OrgDayStat.impressions_sponsored), 0),
                func.coalesce(func.sum(OrgDayStat.profile_visits), 0),
                func.coalesce(func.sum(OrgDayStat.likes_received), 0),
                func.coalesce(func.sum(OrgDayStat.connections), 0),
                func.coalesce(func.sum(OrgDayStat.opportunities), 0),
            ).where(OrgDayStat.org_id == org_id, OrgDayStat.day >= first, OrgDayStat.day <= last)
        )
    ).one()
    organic, sponsored, visits, likes, conns, opps = (int(x) for x in row)
    return {
        "impressions": organic + sponsored,
        "impressions_organic": organic,
        "impressions_sponsored": sponsored,
        "profile_visits": visits,
        "likes": likes,
        "connections": conns,
        "opportunities": opps,
    }


def phase(c: BoostCampaign, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if c.status != "active":
        return c.status
    if c.starts_at and c.starts_at > now:
        return "scheduled"
    return "running"


async def campaign_numbers(session: AsyncSession, c: BoostCampaign) -> dict[str, Any]:
    """Numbers of the campaign so far + organic baseline of the same days before it."""
    now = datetime.now(UTC)
    if not c.starts_at or c.starts_at > now:
        return {"during": None, "baseline": None, "multiplier": None, "days_measured": 0}
    first = _day(c.starts_at)
    last = _day(min(c.ends_at or now, now))
    span = (last - first).days + 1
    during = await stats_between(session, c.org_id, first, last)
    base = await stats_between(
        session, c.org_id, first - timedelta(days=span), first - timedelta(days=1)
    )
    baseline = {"impressions": base["impressions"], "profile_visits": base["profile_visits"]}
    mult = round(during["impressions"] / base["impressions"], 1) if base["impressions"] else None
    return {"during": during, "baseline": baseline, "multiplier": mult, "days_measured": span}


def campaign_view(c: BoostCampaign) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "days": c.days,
        "label": package_label(c.days),
        "amount_cents": c.amount_cents,
        "amount": brl(c.amount_cents),
        "starts_at": iso(c.starts_at),
        "ends_at": iso(c.ends_at),
        "status": c.status,
        "phase": phase(c),
    }


async def campaigns(session: AsyncSession, org_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(BoostCampaign)
            .where(BoostCampaign.org_id == org_id, BoostCampaign.status != "pending")
            .order_by(BoostCampaign.starts_at.desc())
        )
    ).scalars()
    return [{**campaign_view(c), **await campaign_numbers(session, c)} for c in rows]


async def current(session: AsyncSession, org_id: uuid.UUID) -> BoostCampaign | None:
    now = datetime.now(UTC)
    return (
        await session.execute(
            select(BoostCampaign)
            .where(
                BoostCampaign.org_id == org_id,
                BoostCampaign.status == "active",
                BoostCampaign.starts_at <= now,
            )
            .order_by(BoostCampaign.starts_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def summary(session: AsyncSession, org_id: uuid.UUID) -> dict[str, Any] | None:
    """Active campaign with its numbers (Visão Geral, Assinatura)."""
    c = await current(session, org_id)
    if c is None:
        return None
    return {**campaign_view(c), **await campaign_numbers(session, c)}


async def analytics(session: AsyncSession, org_id: uuid.UUID, *, days: int = 30) -> dict[str, Any]:
    """The current (or most recent) campaign vs organic, plus a daily series."""
    c = await current(session, org_id)
    if c is None:
        c = (
            await session.execute(
                select(BoostCampaign)
                .where(BoostCampaign.org_id == org_id, BoostCampaign.status == "finished")
                .order_by(BoostCampaign.ends_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    today = _day(datetime.now(UTC))
    first = today - timedelta(days=days - 1)
    rows = (
        await session.execute(
            select(OrgDayStat)
            .where(OrgDayStat.org_id == org_id, OrgDayStat.day >= first)
            .order_by(OrgDayStat.day)
        )
    ).scalars()
    series = [
        {
            "day": r.day.isoformat(),
            "impressions_organic": r.impressions,
            "impressions_sponsored": r.impressions_sponsored,
            "profile_visits": r.profile_visits,
        }
        for r in rows
    ]
    return {
        "campaign": {**campaign_view(c), **await campaign_numbers(session, c)} if c else None,
        "period": await stats_between(session, org_id, first, today),
        "series": series,
        "baseline_note": "Orgânico = impressões nos mesmos dias antes da campanha.",
        "disclaimer": DISCLAIMER,
    }


# ------------------------------------------------------------------ team panel


async def admin_overview(session: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sales = (
        await session.execute(
            select(Purchase).where(
                Purchase.kind == "boost",
                Purchase.status == "paid",
                Purchase.paid_at >= month_start,
            )
        )
    ).scalars()
    by_pkg = {d: {"sold": 0, "revenue_cents": 0} for d in PACKAGES}
    for p in sales:
        d = int((p.data or {}).get("days") or p.ref or 0)
        slot = by_pkg.setdefault(d, {"sold": 0, "revenue_cents": 0})
        slot["sold"] += 1
        slot["revenue_cents"] += p.amount_cents
    active = (
        await session.execute(
            select(BoostCampaign, Organization)
            .join(Organization, Organization.id == BoostCampaign.org_id)
            .where(BoostCampaign.status == "active")
            .order_by(BoostCampaign.starts_at)
        )
    ).all()
    camp_rows = []
    for c, org in active:
        nums = await campaign_numbers(session, c)
        camp_rows.append({**campaign_view(c), **nums, "org": org_card(org)})
    recent = (
        await session.execute(
            select(BoostCampaign).where(
                BoostCampaign.status.in_(("active", "finished")),
                BoostCampaign.ends_at >= now - timedelta(days=30),
                BoostCampaign.starts_at <= now,
            )
        )
    ).scalars()
    mults = [m for c in recent if (m := (await campaign_numbers(session, c))["multiplier"])]
    impressions_30d = (
        await session.execute(
            select(func.coalesce(func.sum(OrgDayStat.impressions_sponsored), 0)).where(
                OrgDayStat.day >= _day(now) - timedelta(days=29)
            )
        )
    ).scalar_one()
    revenue = sum(v["revenue_cents"] for v in by_pkg.values())
    return {
        "revenue_month_cents": revenue,
        "revenue_month": brl(revenue),
        "packages_sold": sum(v["sold"] for v in by_pkg.values()),
        "packages": [
            {
                "days": d,
                "label": package_label(d),
                "price_cents": PACKAGES.get(d),
                **v,
            }
            for d, v in sorted(by_pkg.items())
        ],
        "active_campaigns": len(camp_rows),
        "campaigns": camp_rows,
        "sponsored_impressions_30d": int(impressions_30d),
        "avg_multiplier": round(sum(mults) / len(mults), 1) if mults else None,
        "disclaimer": "O destaque muda só a posição nas áreas patrocinadas. A compatibilidade "
        "calculada não muda e nenhum resultado é garantido.",
    }


# ------------------------------------------------------------------ background


async def tick(session: AsyncSession, *, org_id: uuid.UUID | None = None) -> int:
    """Finish campaigns at ``ends_at`` and send the result (``boost.finished``)."""
    now = datetime.now(UTC)
    q = select(BoostCampaign).where(BoostCampaign.status == "active", BoostCampaign.ends_at <= now)
    if org_id is not None:
        q = q.where(BoostCampaign.org_id == org_id)
    done = 0
    for c in (await session.execute(q)).scalars():
        nums = await campaign_numbers(session, c)
        c.status = "finished"
        d = nums["during"] or {}
        await notifications.notify(
            session,
            c.org_id,
            kind="boost.finished",
            title=f"Resultado do Brilhar: {d.get('impressions', 0)} impressões",
            link="/app/assinatura",
            departments=AUDIENCE,
            email_vars={
                "impressoes": str(d.get("impressions", 0)),
                "visitas": str(d.get("profile_visits", 0)),
                "conexoes": str(d.get("connections", 0)),
                "oportunidades": str(d.get("opportunities", 0)),
            },
            data={"campaign_id": str(c.id), **{k: v for k, v in d.items()}},
        )
        done += 1
    await session.flush()
    return done


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
            log.exception("boosts tick failed")
        await asyncio.sleep(300)

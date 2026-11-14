"""Visão Geral (scope §14): KPIs by period, filtered by the person's departments.

Every block is included only when the person reaches its area; like KPIs also follow the
intent audience (a Compras user does not see "querem comprar de você"). A person with no
commercial area but with billing (Financeiro) gets the billing KPIs instead.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.deps import Ctx
from app.modules.billing.models import PRICES_CENTS, Invoice
from app.modules.billing.service import brl
from app.modules.boosts import service as boosts
from app.modules.boosts.models import OrgDayStat
from app.modules.discovery.models import DiscoveryAction
from app.modules.events import service as events
from app.modules.intelligence import service as intel
from app.modules.intelligence.engine import blocked_ids
from app.modules.likes.models import Like
from app.modules.matches.models import Match
from app.modules.messaging.models import Conversation, ConversationRead, Message
from app.modules.opportunities.models import Opportunity
from app.modules.organizations.views import iso

PERIODS = (7, 30, 90)
COMMERCIAL_AREAS = ("likes", "matches", "opportunities", "purchases", "sales", "intelligence")
CONFIRMED = ("MATCH_CONFIRMED", "CONNECTION_ACCEPTED", "IN_CONVERSATION")
CLOSED_STAGES = ("won", "lost")


async def _likes(
    session: AsyncSession, ctx: Ctx, since: datetime, blocked: set[uuid.UUID]
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    rows = (
        await session.execute(
            select(Like.source_org_id, Like.target_org_id, Like.intent).where(
                Like.status == "active",
                Like.created_at >= since,
                or_(Like.source_org_id == ctx.org_id, Like.target_org_id == ctx.org_id),
            )
        )
    ).all()
    counts = {
        ("received", "buy"): 0,
        ("received", "sell"): 0,
        ("sent", "buy"): 0,
        ("sent", "sell"): 0,
    }
    for src, tgt, intent in rows:
        other = tgt if src == ctx.org_id else src
        if other in blocked or intent not in ("buy", "sell"):
            continue
        direction = "sent" if src == ctx.org_id else "received"
        counts[(direction, intent)] += 1
    labels = {
        ("received", "buy"): ("likes_received_buy", "Querem comprar de você", "leads de venda"),
        ("received", "sell"): (
            "likes_received_sell",
            "Querem vender para você",
            "possíveis fornecedores",
        ),
        ("sent", "buy"): ("likes_sent_buy", "Você quer comprar de", "curtidas enviadas"),
        ("sent", "sell"): ("likes_sent_sell", "Você quer vender para", "curtidas enviadas"),
    }
    for (direction, intent), (key, label, hint) in labels.items():
        # a received "buy" like is a sales lead (Comercial); a received "sell" like goes to
        # Compras. What I sent with intent "buy" is a Compras matter, "sell" a Comercial one.
        audience_intent = (
            intent if direction == "received" else ("sell" if intent == "buy" else "buy")
        )
        if ctx.sees_intent(audience_intent):
            out[key] = {
                "label": label,
                "value": counts[(direction, intent)],
                "hint": hint,
                "link": "/app/curtidas",
            }
    return out


async def _unread(session: AsyncSession, ctx: Ctx, blocked: set[uuid.UUID]) -> int:
    convs = (
        await session.execute(
            select(Conversation).where(
                or_(Conversation.org_low_id == ctx.org_id, Conversation.org_high_id == ctx.org_id)
            )
        )
    ).scalars()
    mine = set(ctx.user.departments or [])
    allowed = []
    for c in convs:
        other = c.org_high_id if c.org_low_id == ctx.org_id else c.org_low_id
        if other in blocked:
            continue
        depts = (c.departments or {}).get(str(ctx.org_id)) or []
        if ctx.is_owner or not depts or mine.intersection(depts):
            allowed.append(c.id)
    if not allowed:
        return 0
    return (
        await session.execute(
            select(func.count())
            .select_from(Message)
            .outerjoin(
                ConversationRead,
                and_(
                    ConversationRead.conversation_id == Message.conversation_id,
                    ConversationRead.user_id == ctx.user_id,
                ),
            )
            .where(
                Message.conversation_id.in_(allowed),
                or_(Message.sender_org_id.is_(None), Message.sender_org_id != ctx.org_id),
                or_(
                    ConversationRead.last_read_at.is_(None),
                    Message.created_at > ConversationRead.last_read_at,
                ),
            )
        )
    ).scalar_one()


async def _billing(session: AsyncSession, ctx: Ctx) -> dict[str, Any]:
    from app.modules.organizations.views import subscription_view

    sub = ctx.subscription
    view = subscription_view(sub)
    next_charge: dict[str, Any] | None = None
    if sub is not None and sub.status in ("trialing", "active", "past_due"):
        when = sub.trial_end if sub.status == "trialing" else sub.current_period_end
        if sub.kind == "vip":
            when = sub.vip_until if sub.vip_after == "then_charge" else None
        if when and not sub.cancel_at_period_end:
            amount = PRICES_CENTS.get(sub.plan, 0)
            next_charge = {"at": iso(when), "amount_cents": amount, "amount": brl(amount)}
    pending = (
        await session.execute(
            select(func.count()).where(Invoice.org_id == ctx.org_id, Invoice.status == "open")
        )
    ).scalar_one()
    return {
        "subscription": view,
        "next_charge": next_charge,
        "pending_invoices": pending,
        "boost": await boosts.summary(session, ctx.org_id),
    }


async def dashboard(session: AsyncSession, ctx: Ctx, period: int) -> dict[str, Any]:
    now = datetime.now(UTC)
    since = now - timedelta(days=period)
    blocked = await blocked_ids(session, ctx.org_id)
    commercial = any(ctx.can(a) for a in COMMERCIAL_AREAS)
    mode = "commercial" if commercial else ("billing" if ctx.can("billing") else "basic")
    kpis: dict[str, dict[str, Any]] = {}

    if ctx.can("purchases"):
        total = await intel.potential_economy_cents(session, ctx.org_id)
        kpis["potential_economy"] = {
            "label": "Economia potencial",
            "value": total,
            "value_label": brl(total),
            "hint": "por mês · estimativa",
            "link": "/app/compras",
            "estimate": True,
        }

    if ctx.can("matches"):
        n = (
            await session.execute(
                select(Match.org_low_id, Match.org_high_id).where(
                    or_(Match.org_low_id == ctx.org_id, Match.org_high_id == ctx.org_id),
                    Match.status.in_(CONFIRMED),
                    Match.origin != "AI_RECOMMENDATION",
                    func.coalesce(Match.confirmed_at, Match.created_at) >= since,
                )
            )
        ).all()
        kpis["matches_confirmed"] = {
            "label": "Matches confirmados",
            "value": sum(1 for lo, hi in n if (hi if lo == ctx.org_id else lo) not in blocked),
            "link": "/app/matches",
        }

    if ctx.can("likes"):
        kpis.update(await _likes(session, ctx, since, blocked))

    if ctx.can("opportunities"):
        rows = (
            await session.execute(
                select(
                    Opportunity.buyer_org_id,
                    Opportunity.seller_org_id,
                    Opportunity.value_estimate_cents,
                ).where(
                    or_(
                        Opportunity.buyer_org_id == ctx.org_id,
                        Opportunity.seller_org_id == ctx.org_id,
                    ),
                    Opportunity.stage.notin_(CLOSED_STAGES),
                )
            )
        ).all()
        open_rows = [v for b, s, v in rows if (s if b == ctx.org_id else b) not in blocked]
        total = sum(v or 0 for v in open_rows)
        kpis["open_negotiations"] = {
            "label": "Negociações abertas",
            "value": len(open_rows),
            "estimate_cents": total,
            "hint": f"{brl(total)} em jogo (estimativa)" if total else "",
            "link": "/app/oportunidades",
        }

    if ctx.can("company"):
        visits = (
            await session.execute(
                select(func.coalesce(func.sum(OrgDayStat.profile_visits), 0)).where(
                    OrgDayStat.org_id == ctx.org_id, OrgDayStat.day >= since.date()
                )
            )
        ).scalar_one()
        from_boost = (
            await session.execute(
                select(func.count()).where(
                    DiscoveryAction.target_org_id == ctx.org_id,
                    DiscoveryAction.action == "view",
                    DiscoveryAction.sponsored.is_(True),
                    DiscoveryAction.created_at >= since,
                )
            )
        ).scalar_one()
        kpis["profile_visits"] = {
            "label": "Visitas ao perfil",
            "value": int(visits),
            "from_boost": int(from_boost),
            "hint": f"+{from_boost} com Brilhar" if from_boost else "",
            "link": "/app/empresa",
        }

    if ctx.can("messages"):
        kpis["unread_messages"] = {
            "label": "Mensagens não lidas",
            "value": await _unread(session, ctx, blocked),
            "link": "/app/mensagens",
        }

    out: dict[str, Any] = {
        "period": period,
        "mode": mode,
        "kpis": kpis,
        "recommendations": (await intel.list_recommendations(session, ctx, limit=3))
        if commercial
        else [],
        "events": [],
        "boost": None,
        "billing": None,
    }
    if ctx.can("events"):
        out["events"] = (await events.list_upcoming(session, ctx, limit=2))[:2]
    if ctx.can("sales") or ctx.can("billing"):
        out["boost"] = await boosts.summary(session, ctx.org_id)
    if mode == "billing":
        out["billing"] = await _billing(session, ctx)
    if ctx.can("discover"):
        from app.modules.discovery.service import cards_left

        out["discover_new"] = await cards_left(session, ctx)
    return out

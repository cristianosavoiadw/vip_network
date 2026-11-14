"""Likes with direction and intent (scope §7.2, §8, §9, §23).

One active like per direction: liking again with another intent updates the row. Withdrawing
sets ``status = withdrawn`` (existing matches stay; no new match comes from it). Archiving a
sent like sets ``status = archived``; archiving a RECEIVED like is per receiver and is stored as
a ``DiscoveryAction`` "arch_like" (receiver → liker), which hides likes not changed since.

Department visibility (§8.2–8.4, ``permissions.LIKE_AUDIENCE``): a received like is shown to the
departments of its intent (buy → Comercial, sell → Compras); a sent like to the departments of
the mirrored intent (we want to buy → Compras, we want to sell → Comercial).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound
from app.modules.auth.deps import Ctx
from app.modules.catalog.models import Offer
from app.modules.discovery import service as discovery
from app.modules.discovery.models import DiscoveryAction
from app.modules.likes.models import INTENTS, Like
from app.modules.matches import rules, scoring
from app.modules.matches import service as matches
from app.modules.notifications.service import notify
from app.modules.organizations import permissions
from app.modules.organizations.models import Organization
from app.modules.organizations.views import iso, org_card

LIKE_KINDS = {
    "buy": "like.buy_interest",
    "sell": "like.sell_interest",
    "part": "like.part_interest",
    "net": "like.received",
}
LIKE_TITLES = {
    "buy": "{name} quer comprar de vocês",
    "sell": "{name} quer vender para vocês",
    "part": "{name} quer fazer parceria com vocês",
    "net": "{name} curtiu sua empresa",
}
TABS = {
    "compras": (
        (
            "quero_comprar",
            "Quero comprar",
            "Empresas de quem sua empresa quer comprar.",
            "sent",
            "buy",
        ),
        (
            "querem_comprar",
            "Querem comprar de mim",
            "Leads de venda: empresas que querem seus produtos.",
            "received",
            "buy",
        ),
    ),
    "vendas": (
        (
            "quero_vender",
            "Quero vender",
            "Empresas para quem sua empresa quer vender.",
            "sent",
            "sell",
        ),
        (
            "querem_vender",
            "Querem vender para mim",
            "Possíveis fornecedores. Eles não veem suas compras privadas.",
            "received",
            "sell",
        ),
    ),
    "parcerias": (
        ("parcerias_propus", "Parcerias que propus", "", "sent", "part"),
        ("parcerias_recebidas", "Parcerias propostas para mim", "", "received", "part"),
    ),
    "todos": (("todas", "Todas as curtidas", "", None, None),),
}
FILTERS = ("all", "sent", "received", "mutual", "waiting", "matched", "archived")


def like_view(lk: Like) -> dict[str, Any]:
    return {
        "id": str(lk.id),
        "source_org_id": str(lk.source_org_id),
        "target_org_id": str(lk.target_org_id),
        "intent": lk.intent,
        "products": lk.products,
        "offer_id": str(lk.offer_id) if lk.offer_id else None,
        "status": lk.status,
        "created_at": iso(lk.created_at),
        "updated_at": iso(lk.updated_at),
    }


def sees_row(ctx: Ctx, direction: str, intent: str) -> bool:
    return ctx.sees_intent(intent if direction == "received" else rules.FLIP[intent])


# ------------------------------------------------------------------ write


async def like(
    session: AsyncSession,
    ctx: Ctx,
    *,
    target_org_id: uuid.UUID,
    intent: str,
    products: list[str],
    offer_id: uuid.UUID | None,
) -> dict[str, Any]:
    if intent not in INTENTS:
        raise discovery.Unprocessable("Escolha a intenção da curtida.", code="invalid_intent")
    if target_org_id == ctx.org_id:
        raise discovery.Unprocessable("Sua empresa não pode curtir a si mesma.", code="self_like")
    target = await discovery.get_target(session, ctx, target_org_id)
    if await discovery.is_blocked(session, ctx.org_id, target.id):
        raise Forbidden("Não é possível curtir esta empresa.", code="blocked")

    products = [p.strip()[:160] for p in products if p and p.strip()][:10]
    if offer_id is not None:
        offer = await session.get(Offer, offer_id)
        if offer is None or offer.org_id not in (ctx.org_id, target.id):
            raise discovery.Unprocessable("Oferta inválida.", code="invalid_offer")
        if not products:
            products = [offer.name]

    current = (
        await session.execute(
            select(Like).where(
                Like.source_org_id == ctx.org_id,
                Like.target_org_id == target.id,
                Like.status == "active",
            )
        )
    ).scalar_one_or_none()
    is_new = current is None
    changed = is_new or current.intent != intent  # type: ignore[union-attr]
    if current is None:
        current = Like(
            source_org_id=ctx.org_id,
            target_org_id=target.id,
            actor_user_id=ctx.user_id,
            intent=intent,
            products=products,
            offer_id=offer_id,
        )
        session.add(current)
    else:
        current.intent = intent
        current.products = products
        current.offer_id = offer_id
        current.actor_user_id = ctx.user_id
    await session.flush()

    res, match, newly = await matches.apply_like(session, current, source=ctx.org, target=target)
    if is_new:
        await discovery.bump_stats(session, target.id, likes_received=1)
    if changed and not newly:
        await _notify_like(session, current, ctx.org, target)

    if res.kind == "unilateral":
        recommended = await matches.has_open_recommendation(session, ctx.org_id, target.id)
        message = rules.unilateral_message(target.display_name, intent, recommended=recommended)
    else:
        message = res.message
    kind = res.kind
    if kind == "mutual" and matches.is_confirmed(match):
        kind = "match"  # the pair already had a confirmed match; the new like keeps it
        message = "Vocês já têm um match confirmado. A curtida foi atualizada."
    await session.refresh(current)
    return {
        "like": like_view(current),
        "result": {
            "kind": kind,
            "message": message,
            "new_match": newly,
            "match": matches.match_view(match, ctx.org_id, target) if match else None,
        },
    }


async def _notify_like(
    session: AsyncSession, lk: Like, source: Organization, target: Organization
) -> None:
    produto = ", ".join(lk.products) or rules.INTENT_SHORT[lk.intent]
    await notify(
        session,
        target.id,
        kind=LIKE_KINDS[lk.intent],
        title=LIKE_TITLES[lk.intent].format(name=source.display_name),
        body=produto,
        link="/app/curtidas",
        departments=permissions.LIKE_AUDIENCE[lk.intent],
        email_vars={"empresa_origem": source.display_name, "produto": produto},
        data={"like_id": str(lk.id), "org_id": str(source.id), "intent": lk.intent},
    )


async def _own_sent(session: AsyncSession, ctx: Ctx, like_id: uuid.UUID) -> Like:
    lk = await session.get(Like, like_id)
    if lk is None or lk.source_org_id != ctx.org_id:
        raise NotFound("Curtida não encontrada.", code="like_not_found")
    return lk


async def withdraw(session: AsyncSession, ctx: Ctx, like_id: uuid.UUID) -> Like:
    lk = await _own_sent(session, ctx, like_id)
    if lk.status == "active":
        lk.status = "withdrawn"
        await session.flush()
    return lk


async def archive(session: AsyncSession, ctx: Ctx, like_id: uuid.UUID) -> None:
    lk = await session.get(Like, like_id)
    if lk is None or ctx.org_id not in (lk.source_org_id, lk.target_org_id):
        raise NotFound("Curtida não encontrada.", code="like_not_found")
    if lk.source_org_id == ctx.org_id:
        if lk.status == "active":
            lk.status = "archived"
    else:
        session.add(
            DiscoveryAction(
                source_org_id=ctx.org_id,
                target_org_id=lk.source_org_id,
                actor_user_id=ctx.user_id,
                action="arch_like",
            )
        )
    await session.flush()


# ------------------------------------------------------------------ read


async def rows(session: AsyncSession, ctx: Ctx) -> list[dict[str, Any]]:
    """Every like row this person may see, sent and received, with its status."""
    org_id = ctx.org_id
    blocked = await discovery.blocked_ids(session, org_id)
    likes = list(
        (
            await session.execute(
                select(Like).where(
                    or_(
                        (Like.source_org_id == org_id) & Like.status.in_(("active", "archived")),
                        (Like.target_org_id == org_id) & (Like.status == "active"),
                    )
                )
            )
        ).scalars()
    )
    arch_received: dict[uuid.UUID, datetime] = {}
    for tgt, when in await session.execute(
        select(DiscoveryAction.target_org_id, DiscoveryAction.created_at).where(
            DiscoveryAction.source_org_id == org_id, DiscoveryAction.action == "arch_like"
        )
    ):
        arch_received[tgt] = max(when, arch_received.get(tgt, when))

    sent_active = {
        lk.target_org_id for lk in likes if lk.source_org_id == org_id and lk.status == "active"
    }
    recv_active = {lk.source_org_id for lk in likes if lk.target_org_id == org_id}
    others = {lk.target_org_id if lk.source_org_id == org_id else lk.source_org_id for lk in likes}
    others -= blocked
    if not others:
        return []
    orgs = {
        o.id: o
        for o in (
            await session.execute(
                select(Organization).where(
                    Organization.id.in_(others), Organization.status == "active"
                )
            )
        ).scalars()
    }
    pairs = {
        other: m
        for m, other in (
            (m, matches.other_of(m, org_id)) for m in await matches._org_matches(session, org_id)
        )
    }
    compat = await scoring.compatibility_many(session, ctx.org, list(orgs.values()))

    out = []
    for lk in likes:
        direction = "sent" if lk.source_org_id == org_id else "received"
        oid = lk.target_org_id if direction == "sent" else lk.source_org_id
        o = orgs.get(oid)
        if o is None or not sees_row(ctx, direction, lk.intent):
            continue
        m = pairs.get(oid)
        archived = (direction == "sent" and lk.status == "archived") or (
            direction == "received" and oid in arch_received and arch_received[oid] >= lk.updated_at
        )
        if matches.is_confirmed(m):
            status = "matched"
        elif (oid in recv_active) if direction == "sent" else (oid in sent_active):
            status = "mutual"
        else:
            status = "waiting"
        out.append(
            {
                "id": str(lk.id),
                "org": org_card(o),
                "direction": direction,
                "intent": lk.intent,
                "products": lk.products,
                "product": ", ".join(lk.products),
                "offer_id": str(lk.offer_id) if lk.offer_id else None,
                "date": iso(lk.updated_at if direction == "sent" else lk.created_at),
                "status": status,
                "archived": archived,
                "match_id": str(m.id) if m and status == "matched" else None,
                "compat": compat.get(oid, (None, ""))[0],
                "compat_reason": compat.get(oid, (None, ""))[1],
            }
        )
    out.sort(key=lambda r: r["date"] or "", reverse=True)
    return out


def _passes(row: dict[str, Any], f: str) -> bool:
    if f == "archived":
        return row["archived"]
    if row["archived"]:
        return False
    return (
        f == "all"
        or (f == "sent" and row["direction"] == "sent")
        or (f == "received" and row["direction"] == "received")
        or (f in ("mutual", "waiting", "matched") and row["status"] == f)
    )


def _in_tab(row: dict[str, Any], tab: str) -> bool:
    return tab == "todos" or any(
        row["direction"] == d and row["intent"] == i for _, _, _, d, i in TABS[tab]
    )


async def grouped(session: AsyncSession, ctx: Ctx, *, tab: str, f: str) -> dict[str, Any]:
    all_rows = await rows(session, ctx)
    groups = []
    for key, title, sub, direction, intent in TABS[tab]:
        items = [
            r
            for r in all_rows
            if (direction is None or (r["direction"] == direction and r["intent"] == intent))
            and _passes(r, f)
        ]
        groups.append(
            {"key": key, "title": title, "subtitle": sub, "count": len(items), "items": items}
        )
    return {"tab": tab, "filter": f, "groups": groups, "counts": _counts(all_rows)}


def _counts(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    live = [r for r in all_rows if not r["archived"]]
    return {
        "tabs": {t: sum(1 for r in live if _in_tab(r, t)) for t in TABS},
        "filters": {f: sum(1 for r in all_rows if _passes(r, f)) for f in FILTERS},
        "by_tab": {
            t: {f: sum(1 for r in all_rows if _in_tab(r, t) and _passes(r, f)) for f in FILTERS}
            for t in TABS
        },
        "waiting_received": sum(
            1 for r in live if r["direction"] == "received" and r["status"] == "waiting"
        ),
    }


async def summary(session: AsyncSession, ctx: Ctx) -> dict[str, Any]:
    return _counts(await rows(session, ctx))

"""Matches: one row per pair of organizations (scope §9, §10.6, §23).

``apply_like`` is called by the likes service after a like is saved: it reads the other
company's active like, applies ``rules.reciprocity`` and upserts the pair row. A commercial or
partnership match also creates an accepted ``Connection`` (source "match") and notifies both
companies. A confirmed match is never downgraded by a later like.

Archiving is per organization (a ``DiscoveryAction`` "arch_match" from the archiving company),
so the other company keeps seeing the match.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.auth.deps import Ctx
from app.modules.discovery import service as discovery
from app.modules.discovery.models import DiscoveryAction
from app.modules.intelligence.models import Recommendation
from app.modules.likes.models import Like
from app.modules.matches import rules, scoring
from app.modules.matches.models import Match
from app.modules.notifications.service import notify
from app.modules.organizations.models import Organization
from app.modules.organizations.views import iso, org_card

REC_KINDS = {"supplier": "commercial", "buyer": "commercial", "partner": "partnership"}
ORIGIN_LABELS = {
    "MUTUAL_LIKE": "Curtida recíproca",
    "AI_RECOMMENDATION": "Recomendação da IA",
    "MANUAL_CONNECTION": "Conexão direta",
    "EVENT_CONNECTION": "Conheceram-se em evento",
    "STRATEGIC_MATCH": "Match estratégico",
}
STATUS_LABELS = {
    "MUTUAL_INTEREST": "Interesse recíproco",
    "MATCH_CONFIRMED": "Match confirmado",
    "CONNECTION_ACCEPTED": "Conectado",
    "IN_CONVERSATION": "Em conversa",
    "ARCHIVED": "Arquivado",
    "BLOCKED": "Bloqueado",
    "SUGGESTED": "Sugestão · curta para confirmar",
}


def pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


def other_of(m: Match, org_id: uuid.UUID) -> uuid.UUID:
    return m.org_high_id if m.org_low_id == org_id else m.org_low_id


async def pair_match(session: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> Match | None:
    low, high = pair(a, b)
    return (
        await session.execute(
            select(Match).where(Match.org_low_id == low, Match.org_high_id == high)
        )
    ).scalar_one_or_none()


def is_confirmed(m: Match | None) -> bool:
    return bool(m and m.kind in rules.MATCH_KINDS and m.status in rules.CONFIRMED_STATUSES)


def personal_reason(m: Match, org_id: uuid.UUID, other_name: str) -> str:
    """The reason as one side reads it. Built from the kind and the declared products only."""
    product = m.product or "produtos e serviços"
    if m.kind == "commercial":
        if m.buyer_org_id == org_id:
            return f"A {other_name} quer vender {product} e sua empresa quer comprar."
        return f"Sua empresa vende {product} e a {other_name} quer comprar."
    if m.kind == "partnership":
        return f"Sua empresa e a {other_name} querem fazer parceria."
    if m.kind == "mutual_sell":
        return "As duas empresas querem vender uma para a outra. Vale uma conversa."
    if m.kind == "mutual_buy":
        return "As duas empresas querem comprar uma da outra. Confira as ofertas antes."
    return m.reason or "As duas empresas querem se relacionar."


def match_view(m: Match, org_id: uuid.UUID, other: Organization) -> dict[str, Any]:
    i_am_buyer = m.buyer_org_id == org_id if m.buyer_org_id else None
    return {
        "id": str(m.id),
        "source": "match",
        "kind": m.kind,
        "status": m.status,
        "status_label": STATUS_LABELS.get(m.status, m.status),
        "origin": m.origin,
        "origin_label": ORIGIN_LABELS.get(m.origin, m.origin),
        "type_label": rules.type_label(m.kind, i_am_buyer=i_am_buyer),
        "i_am_buyer": i_am_buyer,
        "product": m.product,
        "reason": personal_reason(m, org_id, other.display_name),
        "score": m.score,
        "confirmed": is_confirmed(m),
        "confirmed_at": iso(m.confirmed_at),
        "created_at": iso(m.created_at),
        "updated_at": iso(m.updated_at),
        "org": org_card(other),
    }


def _products(*likes: Like | None) -> str:
    seen: list[str] = []
    for lk in likes:
        for p in (lk.products if lk else []) or []:
            p = (p or "").strip()
            if p and p not in seen:
                seen.append(p)
    return ", ".join(seen)[:300]


async def apply_like(
    session: AsyncSession, like: Like, *, source: Organization, target: Organization
) -> tuple[rules.Reciprocity, Match | None, bool]:
    """Returns (result, match row or None, newly_confirmed)."""
    theirs = (
        await session.execute(
            select(Like).where(
                Like.source_org_id == target.id,
                Like.target_org_id == source.id,
                Like.status == "active",
            )
        )
    ).scalar_one_or_none()
    res = rules.reciprocity(like.intent, theirs.intent if theirs else None)
    if res.kind == "unilateral" or theirs is None:
        return res, None, False

    existing = await pair_match(session, source.id, target.id)
    if existing is not None and is_confirmed(existing) and not res.is_match:
        # a later like never downgrades a confirmed match
        return res, existing, False

    buyer = seller = None
    if res.match_kind == "commercial":
        buyer = source.id if like.intent == "buy" else target.id
        seller = target.id if buyer == source.id else source.id
        buy_like, sell_like = (like, theirs) if like.intent == "buy" else (theirs, like)
        product = _products(buy_like, sell_like)
    else:
        product = _products(like, theirs)

    score, _ = await scoring.compatibility(session, source.id, target.id, use_viewer_private=False)
    seller_name = (source if seller == source.id else target).display_name
    buyer_name = (source if buyer == source.id else target).display_name
    reason = {
        "commercial": f"{seller_name} vende e {buyer_name} quer comprar"
        + (f": {product}." if product else "."),
        "partnership": "As duas empresas demonstraram interesse em parceria.",
        "mutual_sell": "As duas empresas querem vender uma para a outra.",
        "mutual_buy": "As duas empresas querem comprar uma da outra.",
        "relationship": "As duas empresas querem se relacionar.",
    }[res.match_kind or "relationship"]

    was_confirmed = is_confirmed(existing)
    same = (
        was_confirmed
        and existing is not None
        and existing.kind == res.match_kind
        and existing.buyer_org_id == buyer
    )
    low, high = pair(source.id, target.id)
    m = existing or Match(org_low_id=low, org_high_id=high, seen_user_ids=[])
    if existing is None:
        session.add(m)
    m.kind = res.match_kind or "relationship"
    m.status = existing.status if same and existing is not None else res.status or "MUTUAL_INTEREST"
    m.origin = "MUTUAL_LIKE"
    m.buyer_org_id, m.seller_org_id = buyer, seller
    m.product = product
    m.reason = reason
    m.score = score
    newly = res.is_match and not same
    if newly:
        m.confirmed_at = datetime.now(UTC)
        m.seen_user_ids = []
    await session.flush()
    if newly:
        await _on_confirmed(session, m, source, target)
    return res, m, newly


async def _on_confirmed(session: AsyncSession, m: Match, a: Organization, b: Organization) -> None:
    from app.modules.connections import service as connections

    await connections.ensure_accepted(session, a.id, b.id, source="match", requested_by=a.id)
    for me, other in ((a, b), (b, a)):
        is_buyer = m.buyer_org_id == me.id if m.buyer_org_id else None
        label = rules.type_label(m.kind, i_am_buyer=is_buyer)
        await notify(
            session,
            me.id,
            kind="match.confirmed",
            title=f"É match com {other.display_name}!",
            body=f"{label}" + (f" · {m.product}" if m.product else ""),
            link="/app/matches",
            departments=rules.match_departments(m.kind, is_buyer=is_buyer),
            email_vars={
                "empresa_origem": other.display_name,
                "tipo_oportunidade": label,
                "produto": m.product or "a combinar",
            },
            data={"match_id": str(m.id), "org_id": str(other.id)},
        )


# ------------------------------------------------------------------ listing


async def _archived_pairs(session: AsyncSession, org_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await session.execute(
        select(DiscoveryAction.target_org_id).where(
            DiscoveryAction.source_org_id == org_id, DiscoveryAction.action == "arch_match"
        )
    )
    return {r[0] for r in rows}


async def _org_matches(session: AsyncSession, org_id: uuid.UUID) -> list[Match]:
    return list(
        (
            await session.execute(
                select(Match)
                .where(or_(Match.org_low_id == org_id, Match.org_high_id == org_id))
                .order_by(Match.updated_at.desc())
            )
        ).scalars()
    )


async def org_matches(
    session: AsyncSession, org_id: uuid.UUID, *, include_archived: bool = False
) -> list[tuple[Match, Organization]]:
    """The org's matches with the other company, blocks and archived removed."""
    blocked = await discovery.blocked_ids(session, org_id)
    archived = set() if include_archived else await _archived_pairs(session, org_id)
    rows = await _org_matches(session, org_id)
    others = {other_of(m, org_id) for m in rows}
    orgs = (
        {
            o.id: o
            for o in (
                await session.execute(select(Organization).where(Organization.id.in_(others)))
            ).scalars()
        }
        if others
        else {}
    )
    out = []
    for m in rows:
        oid = other_of(m, org_id)
        o = orgs.get(oid)
        if o is None or oid in blocked or o.status != "active" or m.status == "BLOCKED":
            continue
        if not include_archived and (oid in archived or m.status == "ARCHIVED"):
            continue
        out.append((m, o))
    return out


def recommendation_view(r: Recommendation, other: Organization) -> dict[str, Any]:
    kind = REC_KINDS.get(r.kind, "commercial")
    i_am_buyer = True if r.kind == "supplier" else False if r.kind == "buyer" else None
    return {
        "id": str(r.id),
        "source": "recommendation",
        "kind": kind,
        "status": "SUGGESTED",
        "status_label": STATUS_LABELS["SUGGESTED"],
        "origin": "AI_RECOMMENDATION",
        "origin_label": ORIGIN_LABELS["AI_RECOMMENDATION"],
        "type_label": rules.type_label(kind, i_am_buyer=i_am_buyer),
        "i_am_buyer": i_am_buyer,
        "product": r.title,
        "reason": r.body,
        "score": r.score,
        "confirmed": False,
        "confirmed_at": None,
        "created_at": iso(r.created_at),
        "updated_at": iso(r.updated_at),
        "org": org_card(other),
    }


async def list_matches(
    session: AsyncSession, ctx: Ctx, *, origin: str | None = None, archived: bool = False
) -> list[dict[str, Any]]:
    pairs = await org_matches(session, ctx.org_id, include_archived=archived)
    if archived:
        arch = await _archived_pairs(session, ctx.org_id)
        pairs = [(m, o) for m, o in pairs if o.id in arch or m.status == "ARCHIVED"]
    items = [match_view(m, ctx.org_id, o) for m, o in pairs]
    if not archived:
        # AI recommendations (read-only): suggested until a reciprocal like confirms them
        blocked = await discovery.blocked_ids(session, ctx.org_id)
        # a confirmed match (even archived) replaces the suggestion for good
        confirmed = {
            o.id
            for m, o in await org_matches(session, ctx.org_id, include_archived=True)
            if is_confirmed(m)
        }
        recs = (
            await session.execute(
                select(Recommendation, Organization)
                .join(Organization, Organization.id == Recommendation.target_org_id)
                .where(
                    Recommendation.org_id == ctx.org_id,
                    Recommendation.status == "new",
                    Recommendation.kind.in_(list(REC_KINDS)),
                    Organization.status == "active",
                )
                .order_by(Recommendation.created_at.desc())
            )
        ).all()
        seen: set[uuid.UUID] = set()
        for r, o in recs:
            if o.id in blocked or o.id in confirmed or o.id in seen or o.id == ctx.org_id:
                continue
            seen.add(o.id)
            items.append(recommendation_view(r, o))
    if origin:
        items = [i for i in items if i["origin"] == origin.upper()]
    return items


async def unseen(session: AsyncSession, ctx: Ctx) -> list[dict[str, Any]]:
    uid = str(ctx.user_id)
    out = []
    for m, o in await org_matches(session, ctx.org_id):
        if is_confirmed(m) and m.status == "MATCH_CONFIRMED" and uid not in (m.seen_user_ids or []):
            view = match_view(m, ctx.org_id, o)
            view["me"] = org_card(ctx.org)
            out.append(view)
    return out


async def _own_match(session: AsyncSession, ctx: Ctx, match_id: uuid.UUID) -> Match:
    m = await session.get(Match, match_id)
    if m is None or ctx.org_id not in (m.org_low_id, m.org_high_id):
        raise NotFound("Match não encontrado.", code="match_not_found")
    if await discovery.is_blocked(session, m.org_low_id, m.org_high_id):
        raise NotFound("Match não encontrado.", code="match_not_found")
    return m


async def get(session: AsyncSession, ctx: Ctx, match_id: uuid.UUID) -> dict[str, Any]:
    m = await _own_match(session, ctx, match_id)
    other = await session.get(Organization, other_of(m, ctx.org_id))
    assert other is not None
    return match_view(m, ctx.org_id, other)


async def mark_seen(session: AsyncSession, ctx: Ctx, match_id: uuid.UUID) -> None:
    m = await _own_match(session, ctx, match_id)
    uid = str(ctx.user_id)
    if uid not in (m.seen_user_ids or []):
        m.seen_user_ids = [*(m.seen_user_ids or []), uid]
        await session.flush()


async def archive(session: AsyncSession, ctx: Ctx, match_id: uuid.UUID) -> None:
    m = await _own_match(session, ctx, match_id)
    other = other_of(m, ctx.org_id)
    if other not in await _archived_pairs(session, ctx.org_id):
        session.add(
            DiscoveryAction(
                source_org_id=ctx.org_id,
                target_org_id=other,
                actor_user_id=ctx.user_id,
                action="arch_match",
            )
        )
        await session.flush()


async def has_open_recommendation(
    session: AsyncSession, org_id: uuid.UUID, target: uuid.UUID
) -> bool:
    row = await session.execute(
        select(Recommendation.id).where(
            Recommendation.org_id == org_id,
            Recommendation.target_org_id == target,
            Recommendation.status == "new",
        )
    )
    return row.first() is not None

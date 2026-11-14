"""Descobrir (cards), directory, company page, saved companies, blocks and reports
(scope §7.3, §7.4, §23).

Helpers used by likes, matches and connections live here too: ``blocked_ids`` (a block wins
over everything, both directions), ``sponsored_ids`` (active Brilhar campaigns) and
``bump_stats`` (daily counters).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.modules.auth.deps import Ctx
from app.modules.boosts.models import BoostCampaign, OrgDayStat
from app.modules.catalog import service as catalog
from app.modules.catalog.models import Offer, PurchaseNeed
from app.modules.discovery.models import DiscoveryAction, OrgBlock, Report, SavedOrg
from app.modules.likes.models import Like
from app.modules.matches import scoring
from app.modules.organizations.models import Organization
from app.modules.organizations.views import iso, org_card, org_public

SKIP_COOLDOWN = timedelta(days=30)
SPONSORED_FIRST_SLOT = 4  # 0-based: the 5th card, then every SPONSORED_EVERY cards
SPONSORED_EVERY = 5
DIRECTORY_PAGE = 24
DIRECTORY_SPONSORED = 3
REPORT_REASONS = ("spam", "fake", "inappropriate", "fraud", "other")


class Unprocessable(AppError):
    status_code = 422
    code = "unprocessable"


def now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ shared helpers


async def blocked_ids(session: AsyncSession, org_id: uuid.UUID) -> set[uuid.UUID]:
    """Organizations this one blocked or was blocked by."""
    rows = await session.execute(
        select(OrgBlock.source_org_id, OrgBlock.target_org_id).where(
            or_(OrgBlock.source_org_id == org_id, OrgBlock.target_org_id == org_id)
        )
    )
    out: set[uuid.UUID] = set()
    for src, tgt in rows:
        out.add(tgt if src == org_id else src)
    return out


async def is_blocked(session: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> bool:
    row = await session.execute(
        select(OrgBlock.id).where(
            or_(
                and_(OrgBlock.source_org_id == a, OrgBlock.target_org_id == b),
                and_(OrgBlock.source_org_id == b, OrgBlock.target_org_id == a),
            )
        )
    )
    return row.first() is not None


async def sponsored_ids(session: AsyncSession, org_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    ids = list(set(org_ids))
    if not ids:
        return set()
    t = now()
    rows = await session.execute(
        select(BoostCampaign.org_id).where(
            BoostCampaign.org_id.in_(ids),
            BoostCampaign.status == "active",
            or_(BoostCampaign.starts_at.is_(None), BoostCampaign.starts_at <= t),
            or_(BoostCampaign.ends_at.is_(None), BoostCampaign.ends_at > t),
        )
    )
    return {r[0] for r in rows}


async def bump_stats(session: AsyncSession, org_id: uuid.UUID, **inc: int) -> None:
    """Add to today's counters of an organization (``impressions=1``, ``profile_visits=1``…)."""
    if not inc:
        return
    day = now().date()
    stmt = pg_insert(OrgDayStat).values(id=uuid.uuid4(), org_id=org_id, day=day, **inc)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_org_day_stats",
        set_={k: getattr(OrgDayStat, k) + v for k, v in inc.items()},
    )
    try:
        async with session.begin_nested():  # the org may have been deleted meanwhile
            await session.execute(stmt)
    except IntegrityError:
        pass


def open_to(org: Organization, offers: list[Offer], needs: list[PurchaseNeed]) -> list[str]:
    """The "aberta a" chips: sells (published offers), buys (published needs or buying goals),
    part (partnership / distribution goals). Only public or declared data."""
    goals = scoring.norm(" ".join(org.goals or []))
    out = []
    if offers:
        out.append("sell")
    if needs or "fornecedor" in goals or "custo" in goals or "compra" in goals:
        out.append("buy")
    if "parceri" in goals or "distribu" in goals:
        out.append("part")
    return out


async def get_target(session: AsyncSession, ctx: Ctx, target_org_id: uuid.UUID) -> Organization:
    if target_org_id == ctx.org_id:
        raise Unprocessable("Esta é a sua própria empresa.", code="self_target")
    org = await session.get(Organization, target_org_id)
    if org is None or org.status != "active":
        raise NotFound("Empresa não encontrada.", code="org_not_found")
    return org


async def their_likes(
    session: AsyncSession, org_id: uuid.UUID, source_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, Like]:
    """Active likes other organizations sent to ``org_id``."""
    ids = list(set(source_ids))
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Like).where(
                Like.target_org_id == org_id,
                Like.source_org_id.in_(ids),
                Like.status == "active",
            )
        )
    ).scalars()
    return {lk.source_org_id: lk for lk in rows}


def their_like_view(ctx: Ctx, like: Like | None) -> dict[str, Any] | None:
    if like is None or not ctx.sees_intent(like.intent):
        return None
    return {
        "id": str(like.id),
        "intent": like.intent,
        "products": like.products,
        "date": iso(like.created_at),
    }


async def card_views(
    session: AsyncSession, ctx: Ctx, orgs: list[Organization], *, sponsored: set[uuid.UUID]
) -> list[dict[str, Any]]:
    ids = [o.id for o in orgs]
    offers = await catalog.published_offers(session, ids)
    needs = await catalog.published_needs(session, ids)
    compat = await scoring.compatibility_many(session, ctx.org, orgs)
    liked_me = await their_likes(session, ctx.org_id, ids)
    saved = (
        {
            r[0]
            for r in await session.execute(
                select(SavedOrg.target_org_id).where(
                    SavedOrg.org_id == ctx.org_id, SavedOrg.target_org_id.in_(ids)
                )
            )
        }
        if ids
        else set()
    )
    out = []
    for o in orgs:
        value, reason = compat.get(o.id, (0, ""))
        out.append(
            {
                **org_card(o),
                "description": o.description,
                "coverage": o.coverage,
                "products": [x.name for x in offers[o.id][:4]],
                "open_to": open_to(o, offers[o.id], needs[o.id]),
                "compat": value,
                "compat_reason": reason,
                "sponsored": o.id in sponsored,
                "their_like": their_like_view(ctx, liked_me.get(o.id)),
                "saved": o.id in saved,
            }
        )
    return out


def _visible_orgs_query(ctx: Ctx, exclude: set[uuid.UUID]):  # noqa: ANN202
    q = select(Organization).where(
        Organization.status == "active",
        Organization.discoverable.is_(True),
        Organization.id != ctx.org_id,
    )
    if exclude:
        q = q.where(Organization.id.notin_(exclude))
    return q


# ------------------------------------------------------------------ cards (§7.3)


def _diversify(ranked: list[tuple[Organization, int]], window: int = 3) -> list[Organization]:
    """Keep the compat order but avoid two cards of the same sector in a row when one of the
    next ``window`` candidates is from another sector."""
    pool = list(ranked)
    out: list[Organization] = []
    while pool:
        pick = 0
        if out:
            last = out[-1].sector
            for i, (org, _) in enumerate(pool[:window]):
                if org.sector != last:
                    pick = i
                    break
        out.append(pool.pop(pick)[0])
    return out


def place_sponsored(
    organic: list[Organization],
    sponsored: list[tuple[Organization, int]],
    compat: dict[uuid.UUID, int],
) -> list[Organization]:
    """Sponsored companies go to the sponsored slots (5th, 10th, ...). When the list is too short
    for a slot, they take their natural place by compatibility. Their compat never changes."""
    out = list(organic)
    slot = SPONSORED_FIRST_SLOT
    for org, value in sponsored:
        if slot <= len(out):
            out.insert(slot, org)
            slot += SPONSORED_EVERY
        else:
            pos = next((i for i, o in enumerate(out) if compat[o.id] < value), len(out))
            out.insert(pos, org)
    return out


async def _exclusions(session: AsyncSession, ctx: Ctx) -> set[uuid.UUID]:
    """Companies that never show as cards: blocked (both ways), liked, skipped recently."""
    exclude = await blocked_ids(session, ctx.org_id)
    liked = (
        await session.execute(
            select(Like.target_org_id).where(
                Like.source_org_id == ctx.org_id, Like.status == "active"
            )
        )
    ).scalars()
    exclude.update(liked)
    skipped = (
        await session.execute(
            select(DiscoveryAction.target_org_id).where(
                DiscoveryAction.source_org_id == ctx.org_id,
                DiscoveryAction.action == "skip",
                DiscoveryAction.created_at > now() - SKIP_COOLDOWN,
            )
        )
    ).scalars()
    exclude.update(skipped)
    return exclude


async def cards_left(session: AsyncSession, ctx: Ctx) -> int:
    """How many companies the deck still has for this org (no impression is counted)."""
    sub = _visible_orgs_query(ctx, await _exclusions(session, ctx)).subquery()
    return int((await session.execute(select(func.count()).select_from(sub))).scalar_one())


async def cards(
    session: AsyncSession,
    ctx: Ctx,
    *,
    sector: str | None = None,
    state: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    exclude = await _exclusions(session, ctx)
    q = _visible_orgs_query(ctx, exclude)
    if sector:
        q = q.where(Organization.sector == sector)
    if state:
        q = q.where(Organization.state == state.upper())
    candidates = list((await session.execute(q.limit(500))).scalars())
    if not candidates:
        return []
    compat = await scoring.compatibility_many(session, ctx.org, candidates)
    values = {o.id: compat[o.id][0] for o in candidates}
    sponsored = await sponsored_ids(session, values)
    ranked = sorted(
        ((o, values[o.id]) for o in candidates if o.id not in sponsored),
        key=lambda r: (-r[1], r[0].display_name),
    )
    sp = sorted(
        ((o, values[o.id]) for o in candidates if o.id in sponsored),
        key=lambda r: (-r[1], r[0].display_name),
    )
    order = place_sponsored(_diversify(ranked), sp, values)[: max(1, min(limit, 100))]
    out = await card_views(session, ctx, order, sponsored=sponsored)
    for org in order:
        if org.id in sponsored:
            await bump_stats(session, org.id, impressions=1, impressions_sponsored=1)
        else:
            await bump_stats(session, org.id, impressions=1)
    return out


# ------------------------------------------------------------------ actions (§7.4)


async def act(session: AsyncSession, ctx: Ctx, target_org_id: uuid.UUID, action: str) -> dict:
    target = await get_target(session, ctx, target_org_id)
    if action in ("skip", "view"):
        sponsored = bool(await sponsored_ids(session, [target.id]))
        session.add(
            DiscoveryAction(
                source_org_id=ctx.org_id,
                target_org_id=target.id,
                actor_user_id=ctx.user_id,
                action=action,
                sponsored=sponsored,
            )
        )
    elif action == "undo_skip":
        last = (
            await session.execute(
                select(DiscoveryAction)
                .where(
                    DiscoveryAction.source_org_id == ctx.org_id,
                    DiscoveryAction.target_org_id == target.id,
                    DiscoveryAction.action == "skip",
                )
                .order_by(DiscoveryAction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if last is not None:
            await session.delete(last)
    elif action == "save":
        if await is_blocked(session, ctx.org_id, target.id):
            raise NotFound("Empresa não encontrada.", code="org_not_found")
        await session.execute(
            pg_insert(SavedOrg)
            .values(id=uuid.uuid4(), org_id=ctx.org_id, target_org_id=target.id)
            .on_conflict_do_nothing(constraint="uq_saved_orgs")
        )
    elif action == "unsave":
        await session.execute(
            delete(SavedOrg).where(
                SavedOrg.org_id == ctx.org_id, SavedOrg.target_org_id == target.id
            )
        )
    await session.flush()
    return {"ok": True, "action": action, "target_org_id": str(target.id)}


async def saved(session: AsyncSession, ctx: Ctx) -> list[dict[str, Any]]:
    blocked = await blocked_ids(session, ctx.org_id)
    rows = (
        await session.execute(
            select(SavedOrg, Organization)
            .join(Organization, Organization.id == SavedOrg.target_org_id)
            .where(SavedOrg.org_id == ctx.org_id, Organization.status == "active")
            .order_by(SavedOrg.created_at.desc())
        )
    ).all()
    orgs = [o for _, o in rows if o.id not in blocked]
    when = {s.target_org_id: s.created_at for s, _ in rows}
    views = await card_views(
        session, ctx, orgs, sponsored=await sponsored_ids(session, [o.id for o in orgs])
    )
    for v in views:
        v["saved_at"] = iso(when[uuid.UUID(v["id"])])
    return views


async def block(session: AsyncSession, ctx: Ctx, target_org_id: uuid.UUID) -> None:
    target = await get_target(session, ctx, target_org_id)
    await session.execute(
        pg_insert(OrgBlock)
        .values(
            id=uuid.uuid4(),
            source_org_id=ctx.org_id,
            target_org_id=target.id,
            actor_user_id=ctx.user_id,
        )
        .on_conflict_do_nothing(constraint="uq_org_blocks")
    )
    await session.execute(
        delete(SavedOrg).where(SavedOrg.org_id == ctx.org_id, SavedOrg.target_org_id == target.id)
    )
    await session.flush()


async def unblock(session: AsyncSession, ctx: Ctx, target_org_id: uuid.UUID) -> None:
    res = await session.execute(
        delete(OrgBlock).where(
            OrgBlock.source_org_id == ctx.org_id, OrgBlock.target_org_id == target_org_id
        )
    )
    if not res.rowcount:
        raise NotFound("Esta empresa não está bloqueada.", code="block_not_found")


async def my_blocks(session: AsyncSession, ctx: Ctx) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(OrgBlock, Organization)
            .join(Organization, Organization.id == OrgBlock.target_org_id)
            .where(OrgBlock.source_org_id == ctx.org_id)
            .order_by(OrgBlock.created_at.desc())
        )
    ).all()
    return [{**org_card(o), "blocked_at": iso(b.created_at)} for b, o in rows]


async def report(
    session: AsyncSession, ctx: Ctx, target_org_id: uuid.UUID, reason: str, details: str
) -> Report:
    target = await get_target(session, ctx, target_org_id)
    row = Report(
        source_org_id=ctx.org_id,
        target_org_id=target.id,
        actor_user_id=ctx.user_id,
        reason=reason,
        details=details,
    )
    session.add(row)
    await session.flush()
    return row


async def filters(session: AsyncSession, ctx: Ctx) -> dict[str, Any]:
    base = and_(
        Organization.status == "active",
        Organization.discoverable.is_(True),
        Organization.id != ctx.org_id,
    )
    sectors = (
        await session.execute(
            select(Organization.sector, func.count()).where(base).group_by(Organization.sector)
        )
    ).all()
    states = (
        await session.execute(
            select(Organization.state, func.count())
            .where(base, Organization.state != "")
            .group_by(Organization.state)
            .order_by(Organization.state)
        )
    ).all()
    return {
        "sectors": [
            {"value": s, "label": scoring.SECTOR_LABELS.get(s, s), "count": n}
            for s, n in sorted(sectors, key=lambda r: scoring.SECTOR_LABELS.get(r[0], r[0]))
        ],
        "states": [{"value": s, "count": n} for s, n in states],
    }


# ------------------------------------------------------------------ directory


async def directory(
    session: AsyncSession,
    ctx: Ctx,
    *,
    q: str | None = None,
    sector: str | None = None,
    state: str | None = None,
    page: int = 1,
) -> dict[str, Any]:
    exclude = await blocked_ids(session, ctx.org_id)
    query = _visible_orgs_query(ctx, exclude)
    if sector:
        query = query.where(Organization.sector == sector)
    if state:
        query = query.where(Organization.state == state.upper())
    if q and q.strip():
        like = f"%{q.strip()}%"
        offer_orgs = select(Offer.org_id).where(
            Offer.status == "published", or_(Offer.name.ilike(like), Offer.category.ilike(like))
        )
        query = query.where(
            or_(
                Organization.trade_name.ilike(like),
                Organization.legal_name.ilike(like),
                Organization.segment.ilike(like),
                Organization.description.ilike(like),
                Organization.city.ilike(like),
                Organization.id.in_(offer_orgs),
            )
        )
    ids = [r[0] for r in await session.execute(query.with_only_columns(Organization.id))]
    sponsored = await sponsored_ids(session, ids)
    sp_orgs: list[Organization] = []
    if sponsored:
        sp_orgs = list(
            (
                await session.execute(
                    select(Organization)
                    .where(Organization.id.in_(sponsored))
                    .order_by(func.random())
                    .limit(DIRECTORY_SPONSORED)
                )
            ).scalars()
        )
    shown = {o.id for o in sp_orgs}
    organic_ids = [i for i in ids if i not in shown]
    total = len(organic_ids)
    page = max(1, page)
    organic: list[Organization] = []
    if organic_ids:
        organic = list(
            (
                await session.execute(
                    select(Organization)
                    .where(Organization.id.in_(organic_ids))
                    .order_by(
                        func.coalesce(
                            func.nullif(Organization.trade_name, ""), Organization.legal_name
                        )
                    )
                    .offset((page - 1) * DIRECTORY_PAGE)
                    .limit(DIRECTORY_PAGE)
                )
            ).scalars()
        )
    sp_views = await card_views(session, ctx, sp_orgs, sponsored=sponsored) if page == 1 else []
    for org in sp_orgs if page == 1 else []:
        await bump_stats(session, org.id, impressions=1, impressions_sponsored=1)
    return {
        "sponsored": sp_views,
        "items": await card_views(session, ctx, organic, sponsored=sponsored),
        "page": page,
        "page_size": DIRECTORY_PAGE,
        "total": total,
        "pages": max(1, -(-total // DIRECTORY_PAGE)),
    }


# ------------------------------------------------------------------ company page


async def company_page(session: AsyncSession, ctx: Ctx, slug: str) -> dict[str, Any]:
    from app.modules.connections import service as connections
    from app.modules.matches import service as matches

    org = (
        await session.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if org is None or org.status != "active":
        raise NotFound("Empresa não encontrada.", code="org_not_found")
    blocked_by_me = False
    if org.id != ctx.org_id:
        blocks = (
            (
                await session.execute(
                    select(OrgBlock.source_org_id).where(
                        or_(
                            and_(
                                OrgBlock.source_org_id == ctx.org_id,
                                OrgBlock.target_org_id == org.id,
                            ),
                            and_(
                                OrgBlock.source_org_id == org.id,
                                OrgBlock.target_org_id == ctx.org_id,
                            ),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        if org.id in blocks:  # they blocked us: the page does not exist for us
            raise NotFound("Empresa não encontrada.", code="org_not_found")
        blocked_by_me = ctx.org_id in blocks

    offers = (await catalog.published_offers(session, [org.id]))[org.id]
    needs = (await catalog.published_needs(session, [org.id]))[org.id]
    sponsored = bool(await sponsored_ids(session, [org.id]))
    out: dict[str, Any] = {
        "org": org_public(org),
        "offers": [catalog.offer_view(o) for o in offers],
        "published_needs": [catalog.need_public(n) for n in needs],
        "open_to": open_to(org, offers, needs),
        "sponsored": sponsored,
        "is_me": org.id == ctx.org_id,
        "compat": None,
        "compat_reason": "",
        "relationship": None,
    }
    if org.id == ctx.org_id:
        return out

    value, reason = await scoring.compatibility(session, ctx.org_id, org.id)
    out["compat"], out["compat_reason"] = value, reason
    mine = (
        await session.execute(
            select(Like).where(
                Like.source_org_id == ctx.org_id,
                Like.target_org_id == org.id,
                Like.status == "active",
            )
        )
    ).scalar_one_or_none()
    theirs = (await their_likes(session, ctx.org_id, [org.id])).get(org.id)
    match = None if blocked_by_me else await matches.pair_match(session, ctx.org_id, org.id)
    conn = None if blocked_by_me else await connections.pair_connection(session, ctx.org_id, org.id)
    is_saved = (
        await session.execute(
            select(SavedOrg.id).where(
                SavedOrg.org_id == ctx.org_id, SavedOrg.target_org_id == org.id
            )
        )
    ).first() is not None
    out["relationship"] = {
        "my_like": {
            "id": str(mine.id),
            "intent": mine.intent,
            "products": mine.products,
            "date": iso(mine.created_at),
        }
        if mine
        else None,
        "their_like": None if blocked_by_me else their_like_view(ctx, theirs),
        "match": matches.match_view(match, ctx.org_id, org) if match else None,
        "connection": connections.connection_brief(conn, ctx.org_id) if conn else None,
        "saved": is_saved,
        "blocked": blocked_by_me,
    }
    await bump_stats(session, org.id, profile_visits=1)
    session.add(
        DiscoveryAction(
            source_org_id=ctx.org_id,
            target_org_id=org.id,
            actor_user_id=ctx.user_id,
            action="view",
            sponsored=sponsored,
        )
    )
    await session.flush()
    return out

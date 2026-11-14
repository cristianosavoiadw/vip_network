"""Local, rule-based recommendations of one organization (scope §10, §10.3, §16, §23).

``refresh_for(session, org_id)`` rebuilds the cards of the Visão Geral / Inteligência:

- economy: the org's own needs with price paid and monthly volume vs other orgs' PUBLISHED
  offers of the same item with a lower price. Gross = (paid − offer) × qty; net = gross minus an
  estimated freight/adjustment share. Always an estimate. Lives only in the buyer's cards: the
  seller never sees the buyer's price or volume (§10.3).
- supplier: the org's own needs vs other orgs' published offers (no price advantage needed).
- buyer: the org's own published offers vs other orgs' PUBLISHED needs (never private ones;
  never the buyer's price, volume or current supplier).
- partner: complementary sectors, same state first.

Blocked orgs (either direction), the org itself, inactive orgs and mentorship data are never
used. Dismissed cards stay dismissed (same ``data.key``).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.service import brl
from app.modules.catalog.models import Offer, PurchaseNeed
from app.modules.discovery.models import OrgBlock
from app.modules.intelligence.models import Recommendation
from app.modules.organizations.models import Organization

# freight, taxes and other adjustments, as a share of the gross savings (estimate)
ADJUSTMENT_RATE = 0.048
ENGINE_KINDS = ("economy", "supplier", "buyer", "partner")
MAX_PARTNERS = 3

# sectors that usually complement each other (distribution, supply, services)
COMPLEMENTS: dict[str, tuple[str, ...]] = {
    "industria": ("logistica", "varejo", "servicos", "agro"),
    "logistica": ("industria", "varejo", "agro"),
    "varejo": ("industria", "logistica", "tecnologia"),
    "agro": ("industria", "logistica"),
    "tecnologia": ("servicos", "varejo", "saude"),
    "servicos": ("tecnologia", "industria"),
    "saude": ("tecnologia", "servicos"),
    "outros": (),
}
SECTOR_LABEL = {
    "industria": "Indústria",
    "logistica": "Logística",
    "tecnologia": "Tecnologia",
    "servicos": "Serviços",
    "varejo": "Varejo",
    "agro": "Agronegócio",
    "saude": "Saúde",
    "outros": "Outros",
}

STOP = {"de", "da", "do", "das", "dos", "para", "com", "em", "e", "a", "o", "kg", "un"}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _norm(text)) if len(t) > 2 and t not in STOP}


def same_item(cat_a: str, name_a: str, cat_b: str, name_b: str) -> bool:
    """Same category, or (when a category is missing) at least two words of the name in common."""
    if cat_a and cat_b:
        return _norm(cat_a) == _norm(cat_b)
    common = _tokens(name_a) & _tokens(name_b)
    return len(common) >= min(2, len(_tokens(name_a)) or 1)


def economy_math(paid_cents: int, offer_cents: int, qty: int) -> dict[str, Any]:
    gross = (paid_cents - offer_cents) * qty
    adjustment = round(gross * ADJUSTMENT_RATE)
    return {
        "paid_cents": paid_cents,
        "offer_cents": offer_cents,
        "volume_qty": qty,
        "gross_cents": gross,
        "adjustment_cents": adjustment,
        "net_cents": gross - adjustment,
        "pct": round((paid_cents - offer_cents) * 100 / paid_cents) if paid_cents else 0,
        "estimate": True,
        "label": "estimativa",
    }


async def blocked_ids(session: AsyncSession, org_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await session.execute(
        select(OrgBlock.source_org_id, OrgBlock.target_org_id).where(
            or_(OrgBlock.source_org_id == org_id, OrgBlock.target_org_id == org_id)
        )
    )
    out: set[uuid.UUID] = set()
    for src, tgt in rows:
        out.add(tgt if src == org_id else src)
    return out


def _rec(org_id: uuid.UUID, kind: str, target: Organization | None, **kw: Any) -> Recommendation:
    return Recommendation(
        org_id=org_id,
        kind=kind,
        target_org_id=target.id if target else None,
        origin="local",
        status="new",
        **kw,
    )


async def refresh_for(session: AsyncSession, org_id: uuid.UUID) -> list[Recommendation]:
    org = await session.get(Organization, org_id)
    if org is None:
        return []
    skip = await blocked_ids(session, org_id) | {org_id}

    # keys the company already dismissed or acted on stay as they are
    kept = {
        (r.data or {}).get("key")
        for r in (
            await session.execute(
                select(Recommendation).where(
                    Recommendation.org_id == org_id,
                    Recommendation.status != "new",
                    Recommendation.kind.in_(ENGINE_KINDS),
                )
            )
        ).scalars()
    }
    await session.execute(
        delete(Recommendation).where(
            Recommendation.org_id == org_id,
            Recommendation.status == "new",
            Recommendation.origin == "local",
            Recommendation.kind.in_(ENGINE_KINDS),
        )
    )

    others = {
        o.id: o
        for o in (
            await session.execute(
                select(Organization).where(
                    Organization.status == "active", Organization.id.notin_(skip)
                )
            )
        ).scalars()
    }
    offers = [
        o
        for o in (
            await session.execute(
                select(Offer).where(Offer.status == "published", Offer.org_id.in_(others.keys()))
            )
        ).scalars()
    ]
    my_needs = list(
        (
            await session.execute(
                select(PurchaseNeed).where(
                    PurchaseNeed.org_id == org_id, PurchaseNeed.active.is_(True)
                )
            )
        ).scalars()
    )
    my_offers = list(
        (
            await session.execute(
                select(Offer).where(Offer.org_id == org_id, Offer.status == "published")
            )
        ).scalars()
    )
    # only PUBLISHED needs of other companies (§5.2, §16)
    pub_needs = list(
        (
            await session.execute(
                select(PurchaseNeed).where(
                    PurchaseNeed.visibility == "published",
                    PurchaseNeed.active.is_(True),
                    PurchaseNeed.org_id.in_(others.keys()),
                )
            )
        ).scalars()
    )

    new: list[Recommendation] = []
    economy_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()

    def add(rec: Recommendation) -> None:
        if rec.data.get("key") not in kept:
            new.append(rec)

    # ---- economy (own private data, for own eyes only)
    for need in my_needs:
        if not need.price_paid_cents or not need.volume_qty:
            continue
        cheaper = sorted(
            (
                o
                for o in offers
                if o.price_cents
                and o.price_cents < need.price_paid_cents
                and same_item(need.category, need.name, o.category, o.name)
            ),
            key=lambda o: o.price_cents or 0,
        )
        if not cheaper:
            continue
        best = cheaper[0]
        seller = others[best.org_id]
        math = economy_math(need.price_paid_cents, best.price_cents or 0, need.volume_qty)
        unit = need.unit or best.unit or "unidade"
        economy_pairs.add((need.id, seller.id))
        add(
            _rec(
                org_id,
                "economy",
                seller,
                title=f"{need.name}: {brl(math['paid_cents'] - math['offer_cents'])} mais barato por {unit}",
                body=(
                    f"{seller.display_name} oferece o item que você compra. Pode representar até "
                    f"{brl(math['net_cents'])} de economia por mês, já descontando uma estimativa de "
                    "frete e ajustes. É uma estimativa até a confirmação da proposta."
                ),
                score=min(99, 70 + math["pct"]),
                data={
                    "key": f"economy:{need.id}:{best.id}",
                    "need_id": str(need.id),
                    "need_name": need.name,
                    "offer_id": str(best.id),
                    "offer_name": best.name,
                    "unit": unit,
                    "alternatives": len({o.org_id for o in cheaper}),
                    "adjustment_rate": ADJUSTMENT_RATE,
                    **math,
                },
            )
        )

    # ---- supplier (needs vs offers, one card per seller)
    by_seller: dict[uuid.UUID, list[tuple[PurchaseNeed, Offer]]] = {}
    for need in my_needs:
        for o in offers:
            if (need.id, o.org_id) in economy_pairs:
                continue
            if same_item(need.category, need.name, o.category, o.name):
                by_seller.setdefault(o.org_id, []).append((need, o))
    for seller_id, pairs in by_seller.items():
        seller = others[seller_id]
        names = sorted({o.name for _, o in pairs})
        add(
            _rec(
                org_id,
                "supplier",
                seller,
                title=f"{seller.display_name} vende {names[0]}",
                body=f"Oferece {', '.join(names[:3])}, itens que sua empresa compra.",
                score=min(95, 70 + 5 * len(pairs)),
                data={
                    "key": f"supplier:{seller_id}",
                    "offer_ids": [str(o.id) for _, o in pairs],
                    "need_ids": [str(n.id) for n, _ in pairs],
                },
            )
        )

    # ---- buyer (own offers vs published needs; only what the buyer chose to publish)
    by_buyer: dict[uuid.UUID, list[tuple[Offer, PurchaseNeed]]] = {}
    for offer in my_offers:
        for need in pub_needs:
            if same_item(offer.category, offer.name, need.category, need.name):
                by_buyer.setdefault(need.org_id, []).append((offer, need))
    for buyer_id, pairs in by_buyer.items():
        buyer = others[buyer_id]
        need_names = sorted({n.name for _, n in pairs})
        region = next((n.delivery_region for _, n in pairs if n.delivery_region), "")
        add(
            _rec(
                org_id,
                "buyer",
                buyer,
                title=f"{buyer.display_name} procura {need_names[0]}",
                body=(
                    f"Demanda publicada: {', '.join(need_names[:3])}"
                    + (f" (entrega em {region})" if region else "")
                    + ". Você vende itens dessa categoria."
                ),
                score=min(95, 72 + 5 * len(pairs)),
                data={
                    "key": f"buyer:{buyer_id}",
                    "offer_ids": [str(o.id) for o, _ in pairs],
                    "published_need_ids": [str(n.id) for _, n in pairs],
                },
            )
        )

    # ---- partner (complementary sectors)
    wanted = COMPLEMENTS.get(org.sector, ())
    partners = sorted(
        (o for o in others.values() if o.sector in wanted),
        key=lambda o: (o.state != org.state, o.display_name),
    )[:MAX_PARTNERS]
    for p in partners:
        same_state = bool(org.state) and p.state == org.state
        add(
            _rec(
                org_id,
                "partner",
                p,
                title=f"Parceria com {p.display_name}",
                body=(
                    f"Setores complementares: {SECTOR_LABEL.get(org.sector, org.sector)} e "
                    f"{SECTOR_LABEL.get(p.sector, p.sector)}"
                    + (f", ambos em {p.state}" if same_state else "")
                    + ". Pode abrir distribuição, fornecimento ou cooperação."
                ),
                score=80 if same_state else 70,
                data={"key": f"partner:{p.id}"},
            )
        )

    # lock the target companies (FOR SHARE) so none is deleted between the read and the insert
    targets = {r.target_org_id for r in new if r.target_org_id}
    if targets:
        alive = set(
            (
                await session.execute(
                    select(Organization.id)
                    .where(Organization.id.in_(targets))
                    .with_for_update(read=True)
                )
            ).scalars()
        )
        new = [r for r in new if r.target_org_id is None or r.target_org_id in alive]
    session.add_all(new)
    await session.flush()
    return new

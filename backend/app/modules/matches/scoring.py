"""Local compatibility (0–100) between a viewer company and a target company.

Used when the WeOS agents are not configured (PLANO_TECNICO §1) and always for the cards.

Privacy (scope §10.1, SKILL §3): the viewer's OWN private needs may be compared with the
target's PUBLIC offers (the result is shown to the viewer only). The target's needs are read
only when PUBLISHED. The target's private needs are never loaded here, so neither the number
nor the reason text can reveal them. A Brilhar boost is not an input (scope §2.2).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Offer, PurchaseNeed
from app.modules.organizations.models import Organization

SECTOR_LABELS = {
    "industria": "Indústria",
    "logistica": "Logística",
    "tecnologia": "Tecnologia",
    "servicos": "Serviços",
    "varejo": "Varejo",
    "agro": "Agronegócio",
    "saude": "Saúde",
    "outros": "Outros",
}

_STOP = {
    "para",
    "com",
    "sem",
    "produto",
    "produtos",
    "servico",
    "servicos",
    "geral",
    "outros",
    "linha",
    "tipo",
    "industrial",
    "industriais",
    "empresa",
    "empresas",
}
NATIONWIDE = ("brasil", "nacional", "todo o pais", "todos os estados")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def tokens(text: str) -> set[str]:
    out = set()
    for w in re.split(r"[^a-z0-9]+", norm(text)):
        if len(w) < 4 or w in _STOP:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


@dataclass
class Item:
    name: str
    category: str = ""
    text_tokens: set[str] = field(default_factory=set)

    @classmethod
    def of(cls, name: str, category: str = "", extra: str = "") -> Item:
        return cls(name, norm(category).strip(), tokens(f"{name} {extra}"))


@dataclass
class Side:
    org: Organization
    offers: list[Item] = field(default_factory=list)
    needs: list[Item] = field(default_factory=list)  # private included only for the viewer

    @property
    def goals(self) -> str:
        return norm(" ".join(self.org.goals or []))

    @property
    def buys(self) -> bool:
        g = self.goals
        return bool(self.needs) or "fornecedor" in g or "custo" in g

    @property
    def wants_clients(self) -> bool:
        return "cliente" in self.goals or "regio" in self.goals

    @property
    def wants_partners(self) -> bool:
        g = self.goals
        return "distribu" in g or "parceri" in g


def _matches(wanted: list[Item], offered: list[Item]) -> list[Item]:
    """Offered items that answer at least one wanted item (same category or shared word)."""
    hits = []
    for o in offered:
        for w in wanted:
            if (w.category and w.category == o.category) or (w.text_tokens & o.text_tokens):
                hits.append(o)
                break
    return hits


def score(viewer: Side, target: Side) -> tuple[int, str]:
    """Pure scoring. ``target.needs`` must hold PUBLISHED needs only."""
    points = 35
    reasons: list[tuple[int, str]] = []

    supply = _matches(viewer.needs, target.offers)
    if supply:
        points += min(40, 28 + 6 * (len(supply) - 1))
        reasons.append((30, f"Oferece {supply[0].name}, que está entre as compras da sua empresa."))

    # the target's PUBLISHED demands that our offers answer
    demand = _matches(viewer.offers, target.needs)
    if demand:
        points += min(32, 24 + 4 * (len(demand) - 1))
        reasons.append((28, f"Publicou uma demanda de {demand[0].name}, que sua empresa oferece."))

    vo, to = viewer.org, target.org
    if vo.state and vo.state == to.state:
        points += 10
        reasons.append((8, f"Também atua em {to.state}, perto da sua empresa."))
    elif any(n in norm(to.coverage) for n in NATIONWIDE):
        points += 6
        reasons.append((6, "Atende empresas em todo o Brasil."))
    elif vo.state and vo.state.lower() in norm(to.coverage).split():
        points += 6
        reasons.append((6, f"Atende a região da sua empresa ({vo.state})."))

    if vo.sector and vo.sector == to.sector and vo.sector != "outros":
        points += 4
        reasons.append((3, f"As duas empresas são do setor de {SECTOR_LABELS[to.sector]}."))

    if viewer.wants_clients and target.buys:
        points += 6
        reasons.append((10, "Busca fornecedores, e sua empresa quer novos clientes."))
    if viewer.buys and target.offers:
        points += 4
        reasons.append((9, "Tem catálogo publicado, e sua empresa busca fornecedores."))
    if viewer.wants_partners and target.wants_partners:
        points += 8
        reasons.append((12, "As duas empresas procuram parcerias e distribuição."))

    value = max(10, min(98, points))
    if reasons:
        reason = max(reasons, key=lambda r: r[0])[1]
    else:
        where = f"{to.city}/{to.state}" if to.city and to.state else (to.state or "Brasil")
        what = to.segment or SECTOR_LABELS.get(to.sector, "Empresa")
        reason = f"{what} em {where}. Ainda não há sinais fortes de negócio entre vocês."
    return value, reason


# ------------------------------------------------------------------ loading


def _offer_items(offers: Iterable[Offer]) -> list[Item]:
    return [Item.of(o.name, o.category, o.specs) for o in offers]


def _need_items(needs: Iterable[PurchaseNeed]) -> list[Item]:
    return [Item.of(n.name, n.category, n.spec) for n in needs]


async def load_sides(
    session: AsyncSession,
    orgs: list[Organization],
    *,
    private_needs_for: uuid.UUID | None = None,
) -> dict[uuid.UUID, Side]:
    """Sides for many organizations in two queries. Private needs are loaded only for the
    organization ``private_needs_for`` (the viewer itself)."""
    ids = [o.id for o in orgs]
    sides = {o.id: Side(o) for o in orgs}
    if not ids:
        return sides
    offers = (
        await session.execute(
            select(Offer).where(Offer.org_id.in_(ids), Offer.status == "published")
        )
    ).scalars()
    for o in offers:
        sides[o.org_id].offers.extend(_offer_items([o]))
    published = (
        await session.execute(
            select(PurchaseNeed).where(
                PurchaseNeed.org_id.in_(ids),
                PurchaseNeed.active.is_(True),
                PurchaseNeed.visibility == "published",
            )
        )
    ).scalars()
    for n in published:
        if n.org_id != private_needs_for:
            sides[n.org_id].needs.extend(_need_items([n]))
    if private_needs_for is not None and private_needs_for in sides:
        own = (
            await session.execute(
                select(PurchaseNeed).where(
                    PurchaseNeed.org_id == private_needs_for, PurchaseNeed.active.is_(True)
                )
            )
        ).scalars()
        sides[private_needs_for].needs = _need_items(own)
    return sides


async def compatibility_many(
    session: AsyncSession,
    viewer: Organization,
    targets: list[Organization],
    *,
    use_viewer_private: bool = True,
) -> dict[uuid.UUID, tuple[int, str]]:
    others = [t for t in targets if t.id != viewer.id]
    sides = await load_sides(
        session, [viewer, *others], private_needs_for=viewer.id if use_viewer_private else None
    )
    me = sides[viewer.id]
    return {t.id: score(me, sides[t.id]) for t in others}


async def compatibility(
    session: AsyncSession,
    viewer_org_id: uuid.UUID,
    target_org_id: uuid.UUID,
    *,
    use_viewer_private: bool = True,
) -> tuple[int, str]:
    """Compatibility of ``target`` as seen by ``viewer``. ``use_viewer_private=False`` gives a
    value that can be shown to both companies (stored on matches)."""
    viewer = await session.get(Organization, viewer_org_id)
    target = await session.get(Organization, target_org_id)
    if viewer is None or target is None or viewer.id == target.id:
        return 0, ""
    res = await compatibility_many(session, viewer, [target], use_viewer_private=use_viewer_private)
    return res[target.id]

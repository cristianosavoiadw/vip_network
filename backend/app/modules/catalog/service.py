"""Offers (what a company sells, public) and purchase needs (what it buys, private by default).

Scope §6. A need is only ever shown to another organization when ``visibility == "published"``,
and then only name, category, spec and delivery region; price paid, current supplier and volume
need an explicit ``publish_flags`` entry (``price``, ``supplier``, ``volume``).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.modules.catalog.models import Offer, PurchaseNeed
from app.modules.organizations.views import iso

CATEGORIES: tuple[str, ...] = (
    "Alimentos e bebidas",
    "Agronegócio e insumos agrícolas",
    "Automação e robótica",
    "Construção civil e materiais",
    "Consultoria empresarial",
    "Contabilidade e fiscal",
    "Educação e treinamento",
    "Eletroeletrônicos",
    "Embalagens",
    "Energia e utilidades",
    "Equipamentos industriais",
    "Eventos e hospitalidade",
    "Facilities e limpeza",
    "Jurídico",
    "Logística e transporte",
    "Manutenção industrial",
    "Marketing e publicidade",
    "Matérias-primas e químicos",
    "Metalurgia e usinagem",
    "Móveis e escritório",
    "Plásticos e borrachas",
    "Recursos humanos e recrutamento",
    "Saúde e segurança do trabalho",
    "Tecnologia e software",
    "Têxtil e uniformes",
    "Outros",
)

OFFER_KINDS = ("product", "service")
OFFER_STATUSES = ("draft", "published", "paused")
NEED_GOALS = ("reduce_cost", "alternative", "replace", "start")
NEED_VISIBILITY = ("private", "published")
PUBLISH_FLAGS = ("price", "supplier", "volume")

OFFER_FIELDS = (
    "kind",
    "name",
    "description",
    "category",
    "specs",
    "images",
    "price_cents",
    "price_on_request",
    "unit",
    "min_order",
    "conditions",
    "coverage",
    "availability",
    "status",
)
NEED_FIELDS = (
    "name",
    "category",
    "spec",
    "price_paid_cents",
    "unit",
    "volume",
    "volume_qty",
    "frequency",
    "current_supplier",
    "delivery_region",
    "deadline",
    "restrictions",
    "goal",
    "visibility",
    "publish_flags",
    "active",
)


# ------------------------------------------------------------------ views


def offer_view(o: Offer) -> dict[str, Any]:
    """Offers are public by nature (scope §6.1); drafts only reach the owner's list."""
    return {
        "id": str(o.id),
        "org_id": str(o.org_id),
        "kind": o.kind,
        "name": o.name,
        "description": o.description,
        "category": o.category,
        "specs": o.specs,
        "images": o.images,
        "price_cents": None if o.price_on_request else o.price_cents,
        "price_on_request": o.price_on_request,
        "unit": o.unit,
        "min_order": o.min_order,
        "conditions": o.conditions,
        "coverage": o.coverage,
        "availability": o.availability,
        "status": o.status,
        "created_at": iso(o.created_at),
        "updated_at": iso(o.updated_at),
    }


def need_view(n: PurchaseNeed) -> dict[str, Any]:
    """The owner's full view (private data included). Never returned to another org."""
    return {
        "id": str(n.id),
        "name": n.name,
        "category": n.category,
        "spec": n.spec,
        "price_paid_cents": n.price_paid_cents,
        "unit": n.unit,
        "volume": n.volume,
        "volume_qty": n.volume_qty,
        "frequency": n.frequency,
        "current_supplier": n.current_supplier,
        "delivery_region": n.delivery_region,
        "deadline": n.deadline,
        "restrictions": n.restrictions,
        "goal": n.goal,
        "visibility": n.visibility,
        "publish_flags": {k: bool(n.publish_flags.get(k)) for k in PUBLISH_FLAGS},
        "active": n.active,
        "created_at": iso(n.created_at),
        "updated_at": iso(n.updated_at),
    }


def need_public(n: PurchaseNeed) -> dict[str, Any]:
    """A published demand as another company sees it (scope §6.2)."""
    flags = n.publish_flags or {}
    out: dict[str, Any] = {
        "id": str(n.id),
        "name": n.name,
        "category": n.category,
        "spec": n.spec,
        "delivery_region": n.delivery_region,
    }
    if flags.get("price"):
        out["price_paid_cents"] = n.price_paid_cents
        out["unit"] = n.unit
    if flags.get("supplier"):
        out["current_supplier"] = n.current_supplier
    if flags.get("volume"):
        out["volume"] = n.volume
        out["frequency"] = n.frequency
    return out


# ------------------------------------------------------------------ validation


def _clean(data: dict[str, Any], allowed: Iterable[str]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in allowed}


def _check_offer(data: dict[str, Any]) -> None:
    if "kind" in data and data["kind"] not in OFFER_KINDS:
        raise AppError("Tipo inválido: escolha produto ou serviço.", code="invalid_kind")
    if "status" in data and data["status"] not in OFFER_STATUSES:
        raise AppError("Status inválido.", code="invalid_status")
    if "name" in data and not (data["name"] or "").strip():
        raise AppError("Informe o nome da oferta.", code="name_required")


def _check_need(data: dict[str, Any]) -> None:
    if "goal" in data and data["goal"] not in NEED_GOALS:
        raise AppError("Objetivo inválido.", code="invalid_goal")
    if "visibility" in data and data["visibility"] not in NEED_VISIBILITY:
        raise AppError("Visibilidade inválida.", code="invalid_visibility")
    if "name" in data and not (data["name"] or "").strip():
        raise AppError("Informe o item que sua empresa compra.", code="name_required")
    if "publish_flags" in data:
        data["publish_flags"] = {
            k: bool(v) for k, v in (data["publish_flags"] or {}).items() if k in PUBLISH_FLAGS
        }


# ------------------------------------------------------------------ offers


async def list_offers(session: AsyncSession, org_id: uuid.UUID) -> list[Offer]:
    return list(
        (
            await session.execute(
                select(Offer).where(Offer.org_id == org_id).order_by(Offer.created_at.desc())
            )
        ).scalars()
    )


async def _own_offer(session: AsyncSession, org_id: uuid.UUID, offer_id: uuid.UUID) -> Offer:
    offer = await session.get(Offer, offer_id)
    if offer is None or offer.org_id != org_id:
        raise NotFound("Oferta não encontrada.", code="offer_not_found")
    return offer


async def create_offer(session: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]) -> Offer:
    data = _clean(data, OFFER_FIELDS)
    _check_offer(data)
    offer = Offer(org_id=org_id, **data)
    session.add(offer)
    await session.flush()
    return offer


async def update_offer(
    session: AsyncSession, org_id: uuid.UUID, offer_id: uuid.UUID, data: dict[str, Any]
) -> Offer:
    offer = await _own_offer(session, org_id, offer_id)
    data = _clean(data, OFFER_FIELDS)
    _check_offer(data)
    for k, v in data.items():
        setattr(offer, k, v)
    await session.flush()
    return offer


async def delete_offer(session: AsyncSession, org_id: uuid.UUID, offer_id: uuid.UUID) -> None:
    offer = await _own_offer(session, org_id, offer_id)
    await session.delete(offer)
    await session.flush()


async def published_offers(
    session: AsyncSession, org_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[Offer]]:
    ids = list(set(org_ids))
    out: dict[uuid.UUID, list[Offer]] = {i: [] for i in ids}
    if not ids:
        return out
    rows = (
        await session.execute(
            select(Offer)
            .where(Offer.org_id.in_(ids), Offer.status == "published")
            .order_by(Offer.created_at.asc())
        )
    ).scalars()
    for o in rows:
        out[o.org_id].append(o)
    return out


# ------------------------------------------------------------------ purchase needs


async def list_needs(session: AsyncSession, org_id: uuid.UUID) -> list[PurchaseNeed]:
    return list(
        (
            await session.execute(
                select(PurchaseNeed)
                .where(PurchaseNeed.org_id == org_id)
                .order_by(PurchaseNeed.created_at.desc())
            )
        ).scalars()
    )


async def _own_need(session: AsyncSession, org_id: uuid.UUID, need_id: uuid.UUID) -> PurchaseNeed:
    need = await session.get(PurchaseNeed, need_id)
    if need is None or need.org_id != org_id:
        raise NotFound("Item de compra não encontrado.", code="need_not_found")
    return need


async def create_need(
    session: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]
) -> PurchaseNeed:
    data = _clean(data, NEED_FIELDS)
    data.setdefault("visibility", "private")
    _check_need(data)
    need = PurchaseNeed(org_id=org_id, **data)
    session.add(need)
    await session.flush()
    return need


async def update_need(
    session: AsyncSession, org_id: uuid.UUID, need_id: uuid.UUID, data: dict[str, Any]
) -> PurchaseNeed:
    need = await _own_need(session, org_id, need_id)
    data = _clean(data, NEED_FIELDS)
    _check_need(data)
    for k, v in data.items():
        setattr(need, k, v)
    await session.flush()
    return need


async def delete_need(session: AsyncSession, org_id: uuid.UUID, need_id: uuid.UUID) -> None:
    need = await _own_need(session, org_id, need_id)
    await session.delete(need)
    await session.flush()


async def published_needs(
    session: AsyncSession, org_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[PurchaseNeed]]:
    """Only the demands a company chose to publish. Private needs never leave this module
    except to their owner (``list_needs``) and the owner's own scoring."""
    ids = list(set(org_ids))
    out: dict[uuid.UUID, list[PurchaseNeed]] = {i: [] for i in ids}
    if not ids:
        return out
    rows = (
        await session.execute(
            select(PurchaseNeed)
            .where(
                PurchaseNeed.org_id.in_(ids),
                PurchaseNeed.visibility == "published",
                PurchaseNeed.active.is_(True),
            )
            .order_by(PurchaseNeed.created_at.asc())
        )
    ).scalars()
    for n in rows:
        out[n.org_id].append(n)
    return out

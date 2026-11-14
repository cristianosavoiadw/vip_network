"""/offers (what we sell, public), /purchase-needs (what we buy, private) and
/catalog/categories."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.modules.auth.deps import Ctx, DbSession, area_any_status
from app.modules.catalog import service
from app.modules.catalog.service import need_view, offer_view

router = APIRouter(tags=["catalog"])

# also during sign-up (onboarding steps 6 and 7 register offers and purchases)
CompanyCtx = Annotated[Ctx, Depends(area_any_status("company"))]
PurchasesCtx = Annotated[Ctx, Depends(area_any_status("purchases"))]


class OfferIn(BaseModel):
    kind: Literal["product", "service"] = "product"
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=3000)
    category: str = Field(default="", max_length=80)
    specs: str = Field(default="", max_length=3000)
    images: list[str] = Field(default_factory=list, max_length=10)
    price_cents: int | None = Field(default=None, ge=0)
    price_on_request: bool = True
    unit: str = Field(default="", max_length=30)
    min_order: str = Field(default="", max_length=60)
    conditions: str = Field(default="", max_length=2000)
    coverage: str = Field(default="", max_length=120)
    availability: str = Field(default="", max_length=60)
    status: Literal["draft", "published", "paused"] = "published"


class OfferPatch(BaseModel):
    kind: Literal["product", "service"] | None = None
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=3000)
    category: str | None = Field(default=None, max_length=80)
    specs: str | None = Field(default=None, max_length=3000)
    images: list[str] | None = Field(default=None, max_length=10)
    price_cents: int | None = Field(default=None, ge=0)
    price_on_request: bool | None = None
    unit: str | None = Field(default=None, max_length=30)
    min_order: str | None = Field(default=None, max_length=60)
    conditions: str | None = Field(default=None, max_length=2000)
    coverage: str | None = Field(default=None, max_length=120)
    availability: str | None = Field(default=None, max_length=60)
    status: Literal["draft", "published", "paused"] | None = None


class PublishFlags(BaseModel):
    price: bool = False
    supplier: bool = False
    volume: bool = False


class NeedIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(default="", max_length=80)
    spec: str = Field(default="", max_length=3000)
    price_paid_cents: int | None = Field(default=None, ge=0)
    unit: str = Field(default="", max_length=30)
    volume: str = Field(default="", max_length=60)
    volume_qty: int | None = Field(default=None, ge=0)
    frequency: str = Field(default="", max_length=40)
    current_supplier: str = Field(default="", max_length=160)
    delivery_region: str = Field(default="", max_length=120)
    deadline: str = Field(default="", max_length=60)
    restrictions: str = Field(default="", max_length=2000)
    goal: Literal["reduce_cost", "alternative", "replace", "start"] = "reduce_cost"
    visibility: Literal["private", "published"] = "private"
    publish_flags: PublishFlags = Field(default_factory=PublishFlags)
    active: bool = True


class NeedPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    spec: str | None = Field(default=None, max_length=3000)
    price_paid_cents: int | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=30)
    volume: str | None = Field(default=None, max_length=60)
    volume_qty: int | None = Field(default=None, ge=0)
    frequency: str | None = Field(default=None, max_length=40)
    current_supplier: str | None = Field(default=None, max_length=160)
    delivery_region: str | None = Field(default=None, max_length=120)
    deadline: str | None = Field(default=None, max_length=60)
    restrictions: str | None = Field(default=None, max_length=2000)
    goal: Literal["reduce_cost", "alternative", "replace", "start"] | None = None
    visibility: Literal["private", "published"] | None = None
    publish_flags: PublishFlags | None = None
    active: bool | None = None


# ------------------------------------------------------------------ categories


@router.get("/catalog/categories")
async def categories(ctx: Annotated[Ctx, Depends(area_any_status("overview"))]) -> list[str]:
    return list(service.CATEGORIES)


# ------------------------------------------------------------------ offers


@router.get("/offers")
async def list_offers(session: DbSession, ctx: CompanyCtx) -> list[dict[str, Any]]:
    return [offer_view(o) for o in await service.list_offers(session, ctx.org_id)]


@router.post("/offers")
async def create_offer(body: OfferIn, session: DbSession, ctx: CompanyCtx) -> dict[str, Any]:
    return offer_view(await service.create_offer(session, ctx.org_id, body.model_dump()))


@router.patch("/offers/{offer_id}")
async def update_offer(
    offer_id: uuid.UUID, body: OfferPatch, session: DbSession, ctx: CompanyCtx
) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    return offer_view(await service.update_offer(session, ctx.org_id, offer_id, data))


@router.delete("/offers/{offer_id}")
async def delete_offer(offer_id: uuid.UUID, session: DbSession, ctx: CompanyCtx) -> dict[str, bool]:
    await service.delete_offer(session, ctx.org_id, offer_id)
    return {"ok": True}


# ------------------------------------------------------------------ purchase needs (private)


@router.get("/purchase-needs")
async def list_needs(session: DbSession, ctx: PurchasesCtx) -> list[dict[str, Any]]:
    return [need_view(n) for n in await service.list_needs(session, ctx.org_id)]


@router.post("/purchase-needs")
async def create_need(body: NeedIn, session: DbSession, ctx: PurchasesCtx) -> dict[str, Any]:
    return need_view(await service.create_need(session, ctx.org_id, body.model_dump()))


@router.patch("/purchase-needs/{need_id}")
async def update_need(
    need_id: uuid.UUID, body: NeedPatch, session: DbSession, ctx: PurchasesCtx
) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    return need_view(await service.update_need(session, ctx.org_id, need_id, data))


@router.delete("/purchase-needs/{need_id}")
async def delete_need(need_id: uuid.UUID, session: DbSession, ctx: PurchasesCtx) -> dict[str, bool]:
    await service.delete_need(session, ctx.org_id, need_id)
    return {"ok": True}

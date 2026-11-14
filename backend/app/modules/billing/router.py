"""/billing (company side: quote, card, subscribe, cancel, portal, invoices) and the Stripe
webhook. Access to these routes never depends on the subscription being valid (the company
must always be able to pay)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.deps import Ctx, DbSession, area_any_status
from app.modules.billing import service
from app.modules.billing.models import PRICES_CENTS
from app.modules.invites import service as invites
from app.modules.organizations.views import iso, subscription_view
from app.modules.settings import service as settings_service

router = APIRouter(prefix="/billing", tags=["billing"])
BillingCtx = Annotated[Ctx, Depends(area_any_status("billing"))]


class PlanIn(BaseModel):
    plan: str


class SubscribeIn(BaseModel):
    plan: str
    payment_method_id: str | None = None


@router.get("/config")
async def config() -> dict[str, Any]:
    s = get_settings()
    return {
        "simulated": not s.stripe_live,
        "publishable_key": getattr(s, "stripe_publishable_key", ""),
        "prices": {k: v for k, v in PRICES_CENTS.items()},
        "trial_hours": s.trial_hours,
    }


@router.get("/quote")
async def quote(plan: str, ctx: BillingCtx, session: DbSession) -> dict[str, Any]:
    """What the user sees before confirming: the date and amount of the first charge."""
    if ctx.org.entry == "invite":
        conf = await settings_service.get(session, "access")
        months = settings_service.vip_months(conf)
        from datetime import UTC, datetime

        until = service.add_months(datetime.now(UTC), months)
        return {
            "plan": plan,
            "vip": True,
            "vip_months": months,
            "vip_until": until.isoformat(),
            "after": "invite_only" if conf["mode"] == "invite" else "then_charge",
            "amount_cents": PRICES_CENTS.get(plan, 0),
            "amount": service.brl(PRICES_CENTS.get(plan, 0)),
            "today_cents": 0,
            "first_charge_at": None if conf["mode"] == "invite" else until.isoformat(),
        }
    trial = not await service.has_trial_claim(session, ctx.org.cnpj)
    return {**service.quote(plan, trial=trial), "vip": False}


@router.post("/setup-intent")
async def setup_intent(ctx: BillingCtx, session: DbSession) -> dict[str, Any]:
    return await service.setup_intent(session, ctx.org, ctx.user)


@router.post("/subscribe")
async def subscribe(body: SubscribeIn, ctx: BillingCtx, session: DbSession) -> dict[str, Any]:
    vip_months = None
    vip_after = ""
    if ctx.org.entry == "invite":
        conf = await settings_service.get(session, "access")
        vip_months = settings_service.vip_months(conf)
        vip_after = "invite_only" if conf["mode"] == "invite" else "then_charge"
    sub = await service.subscribe(
        session,
        ctx.org,
        ctx.user,
        plan=body.plan,
        payment_method_id=body.payment_method_id,
        vip_months=vip_months,
        vip_after=vip_after,
    )
    if ctx.org.onboarding_completed_at is None:
        ctx.org.onboarding_step = max(ctx.org.onboarding_step, 5)
    return subscription_view(sub) or {}


@router.get("/subscription")
async def subscription(ctx: BillingCtx, session: DbSession) -> dict[str, Any]:
    sub = await service.get_subscription(session, ctx.org_id)
    view = subscription_view(sub)
    inviter = None
    if ctx.org.invited_by_org_id:
        from app.modules.organizations.models import Organization

        o = await session.get(Organization, ctx.org.invited_by_org_id)
        inviter = o.display_name if o else None
    conf = await settings_service.get(session, "access")
    return {
        "subscription": view,
        "amounts": {k: service.brl(v) for k, v in PRICES_CENTS.items()},
        "invited_by": inviter,
        "entry": ctx.org.entry,
        "mode": conf["mode"],
        "invites": (await invites.summary(session, ctx.org))["remaining"],
    }


@router.post("/plan")
async def change_plan(body: PlanIn, ctx: BillingCtx, session: DbSession) -> dict[str, Any]:
    return subscription_view(await service.change_plan(session, ctx.org_id, body.plan)) or {}


@router.post("/cancel")
async def cancel(ctx: BillingCtx, session: DbSession) -> dict[str, Any]:
    sub = await service.cancel(session, ctx.org_id)
    from app.modules.notifications import service as notifications

    detail = (
        "Nenhuma cobrança será feita. O acesso continua até o fim do período grátis."
        if sub.status == "canceled"
        else "O acesso continua até o fim do período já pago."
    )
    await notifications.notify(
        session,
        ctx.org_id,
        kind="billing.canceled",
        title="Assinatura cancelada",
        link="/app/assinatura",
        departments=("diretoria", "financeiro"),
        email_vars={"detalhe": detail},
    )
    return subscription_view(sub) or {}


@router.post("/reactivate")
async def reactivate(ctx: BillingCtx, session: DbSession) -> dict[str, Any]:
    return subscription_view(await service.reactivate(session, ctx.org, ctx.user)) or {}


@router.post("/portal")
async def portal(ctx: BillingCtx, session: DbSession) -> dict[str, Any]:
    return await service.portal_url(session, ctx.org_id)


@router.get("/invoices")
async def list_invoices(ctx: BillingCtx, session: DbSession) -> list[dict[str, Any]]:
    return [
        {
            "id": str(i.id),
            "amount_cents": i.amount_cents,
            "amount": service.brl(i.amount_cents),
            "status": i.status,
            "description": i.description,
            "period_start": iso(i.period_start),
            "period_end": iso(i.period_end),
            "paid_at": iso(i.paid_at),
            "url": i.hosted_url,
        }
        for i in await service.invoices(session, ctx.org_id)
    ]


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request, session: DbSession, stripe_signature: str = Header(default="")
) -> dict[str, str]:
    if not get_settings().stripe_webhook_secret:
        raise AppError("Webhook do Stripe não configurado.", code="webhook_off")
    result = await service.handle_webhook(session, await request.body(), stripe_signature)
    return {"result": result}

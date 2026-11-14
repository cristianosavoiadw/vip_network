"""Subscriptions (trial and VIP), one-off purchases and the Stripe webhook (scope §2, §25).

Rules covered by tests:
- trial_end = subscription creation (UTC) + 168 h, shown before checkout;
- one trial per CNPJ, ever (``TrialClaim``);
- canceling during the trial cancels in Stripe right away (no first charge) and keeps access
  until the trial ends;
- VIP plan: free until ``vip_until``; ``then_charge`` charges the chosen plan after it,
  ``invite_only`` never charges (Stripe ``cancel_at`` = vip_until), renewal by platform rules;
- webhooks: signature verified, idempotent by event id, out-of-order safe (re-read from Stripe).

Without ``VIP_STRIPE_SECRET_KEY`` (dev/tests) every call is simulated locally with the same
states Stripe would answer; the background loop plays the role of Stripe's clock.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, Conflict, NotFound
from app.modules.auth.models import User
from app.modules.billing import gateway
from app.modules.billing.models import (
    PRICES_CENTS,
    Invoice,
    Purchase,
    StripeEvent,
    Subscription,
    TrialClaim,
)
from app.modules.organizations.models import Organization

log = logging.getLogger("vip.billing")
PLANS = ("monthly", "annual")


def brl(cents: int) -> str:
    whole, frac = divmod(int(cents), 100)
    return f"R$ {whole:,}".replace(",", ".") + f",{frac:02d}"


def _live() -> bool:
    return get_settings().stripe_live


def _price_id(plan: str) -> str:
    s = get_settings()
    return s.stripe_price_monthly if plan == "monthly" else s.stripe_price_annual


def _ts(value: Any) -> datetime | None:
    return datetime.fromtimestamp(int(value), UTC) if value else None


def trial_end_from(created: datetime) -> datetime:
    return created + timedelta(hours=get_settings().trial_hours)


def add_months(when: datetime, months: int) -> datetime:
    month = when.month - 1 + months
    year = when.year + month // 12
    month = month % 12 + 1
    day = min(
        when.day,
        [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return when.replace(year=year, month=month, day=day)


async def get_subscription(session: AsyncSession, org_id: uuid.UUID) -> Subscription | None:
    return (
        await session.execute(select(Subscription).where(Subscription.org_id == org_id))
    ).scalar_one_or_none()


async def has_trial_claim(session: AsyncSession, cnpj: str) -> bool:
    return await session.get(TrialClaim, cnpj) is not None


def quote(plan: str, *, now: datetime | None = None, trial: bool = True) -> dict[str, Any]:
    """What the checkout shows before the user confirms (§2.1)."""
    if plan not in PLANS:
        raise AppError("Plano inválido.", code="invalid_plan")
    now = now or datetime.now(UTC)
    end = trial_end_from(now) if trial else now
    return {
        "plan": plan,
        "amount_cents": PRICES_CENTS[plan],
        "amount": brl(PRICES_CENTS[plan]),
        "today_cents": 0 if trial else PRICES_CENTS[plan],
        "trial": trial,
        "trial_end": end.isoformat(),
        "first_charge_at": end.isoformat(),
    }


async def _ensure_customer(
    session: AsyncSession, org: Organization, user: User, sub: Subscription
) -> None:
    if sub.stripe_customer_id:
        return
    if _live():
        c = await gateway.create_customer(
            name=org.display_name, email=user.email, cnpj=org.cnpj, org_id=str(org.id)
        )
        sub.stripe_customer_id = c["id"]
    else:
        sub.stripe_customer_id = f"sim_cus_{secrets.token_hex(6)}"


async def setup_intent(session: AsyncSession, org: Organization, user: User) -> dict[str, Any]:
    """Client secret for Stripe Elements (live) or a marker for the simulated card form."""
    sub = await get_subscription(session, org.id) or Subscription(org_id=org.id)
    if sub.id is None:
        session.add(sub)
    await _ensure_customer(session, org, user, sub)
    await session.flush()
    if not _live():
        return {"simulated": True, "client_secret": ""}
    si = await gateway.setup_intent(sub.stripe_customer_id)
    return {"simulated": False, "client_secret": si["client_secret"]}


async def _card(sub: Subscription, payment_method_id: str | None) -> None:
    if not payment_method_id or not _live():
        sub.card_brand, sub.card_last4, sub.card_exp = "visa", "4242", "12/2029"
        return
    pm = await gateway.attach_default_card(sub.stripe_customer_id, payment_method_id)
    card = pm.get("card") or {}
    sub.card_brand = str(card.get("brand", ""))
    sub.card_last4 = str(card.get("last4", ""))
    sub.card_exp = f"{int(card.get('exp_month', 0)):02d}/{card.get('exp_year', '')}"


async def subscribe(
    session: AsyncSession,
    org: Organization,
    user: User,
    *,
    plan: str,
    payment_method_id: str | None,
    vip_months: int | None = None,
    vip_after: str = "",
) -> Subscription:
    """Start the standard plan (7-day trial, once per CNPJ) or the VIP plan (invited)."""
    if plan not in PLANS:
        raise AppError("Plano inválido.", code="invalid_plan")
    sub = await get_subscription(session, org.id)
    if (
        sub is not None
        and sub.stripe_subscription_id
        and sub.status not in ("canceled", "incomplete")
    ):
        raise Conflict("A empresa já tem uma assinatura ativa.", code="already_subscribed")
    if sub is None:
        sub = Subscription(org_id=org.id)
        session.add(sub)
    await _ensure_customer(session, org, user, sub)
    await _card(sub, payment_method_id)
    now = datetime.now(UTC)
    sub.plan = plan
    sub.trial_start = now
    sub.canceled_at = None
    sub.cancel_at_period_end = False

    cancel_at: datetime | None = None
    if vip_months:
        sub.kind = "vip"
        sub.vip_until = add_months(now, vip_months)
        sub.vip_after = vip_after or "then_charge"
        sub.trial_end = sub.vip_until
        if sub.vip_after == "invite_only":
            cancel_at = sub.vip_until  # never charged automatically
    else:
        sub.kind = "standard"
        sub.vip_until = None
        sub.vip_after = ""
        trial = not await has_trial_claim(session, org.cnpj)
        sub.trial_end = trial_end_from(now) if trial else None
        if trial:
            session.add(TrialClaim(cnpj=org.cnpj, org_id=org.id, claimed_at=now))

    if _live():
        remote = await gateway.create_subscription(
            customer_id=sub.stripe_customer_id,
            price_id=_price_id(plan),
            trial_end=sub.trial_end,
            cancel_at=cancel_at,
            org_id=str(org.id),
            kind=sub.kind,
        )
        apply_remote(sub, remote)
    else:
        sub.stripe_subscription_id = f"sim_sub_{secrets.token_hex(6)}"
        if sub.trial_end:
            sub.status = "trialing"
            sub.current_period_end = sub.trial_end
        else:  # second sign-up of the same CNPJ: no trial, charged now
            sub.status = "active"
            sub.current_period_end = add_months(now, 12 if plan == "annual" else 1)
            await _record_sim_invoice(session, sub, now)
    await session.flush()
    return sub


def apply_remote(sub: Subscription, remote: Any) -> None:
    sub.stripe_subscription_id = remote["id"]
    sub.status = str(remote["status"])
    sub.trial_end = _ts(remote.get("trial_end")) or sub.trial_end
    sub.current_period_end = _ts(remote.get("current_period_end")) or sub.current_period_end
    sub.cancel_at_period_end = bool(remote.get("cancel_at_period_end"))
    sub.canceled_at = _ts(remote.get("canceled_at"))
    sub.last_synced_at = datetime.now(UTC)


async def _record_sim_invoice(session: AsyncSession, sub: Subscription, when: datetime) -> Invoice:
    inv = Invoice(
        org_id=sub.org_id,
        stripe_invoice_id=f"sim_in_{secrets.token_hex(8)}",
        amount_cents=PRICES_CENTS[sub.plan],
        status="paid",
        description=f"VIP Network {'Anual' if sub.plan == 'annual' else 'Mensal'}",
        period_start=when,
        period_end=sub.current_period_end,
        paid_at=when,
    )
    session.add(inv)
    await session.flush()
    return inv


async def cancel(session: AsyncSession, org_id: uuid.UUID) -> Subscription:
    sub = await get_subscription(session, org_id)
    if sub is None or sub.status in ("canceled", "incomplete"):
        raise NotFound("Não há assinatura ativa para cancelar.", code="no_subscription")
    now = datetime.now(UTC)
    in_free_time = sub.status == "trialing" or (
        sub.kind == "vip" and sub.vip_until and sub.vip_until > now
    )
    if in_free_time:
        # cancel in Stripe now: the first charge can never happen (§2.1, §25)
        if _live():
            await gateway.cancel_now(sub.stripe_subscription_id)
        sub.status = "canceled"
        sub.canceled_at = now
    else:
        if _live():
            await gateway.cancel_at_period_end(sub.stripe_subscription_id, True)
        sub.cancel_at_period_end = True
    await session.flush()
    return sub


async def reactivate(session: AsyncSession, org: Organization, user: User) -> Subscription:
    sub = await get_subscription(session, org.id)
    if sub is None:
        raise NotFound("Não há assinatura.", code="no_subscription")
    now = datetime.now(UTC)
    if sub.cancel_at_period_end and sub.status != "canceled":
        if _live():
            await gateway.cancel_at_period_end(sub.stripe_subscription_id, False)
        sub.cancel_at_period_end = False
        return sub
    if sub.status != "canceled":
        return sub
    # canceled during free time: resume with the same end date (no new trial)
    free_end = sub.vip_until if sub.kind == "vip" else sub.trial_end
    end = free_end if free_end and free_end > now else None
    if _live():
        remote = await gateway.create_subscription(
            customer_id=sub.stripe_customer_id,
            price_id=_price_id(sub.plan),
            trial_end=end,
            cancel_at=sub.vip_until
            if sub.kind == "vip" and sub.vip_after == "invite_only"
            else None,
            org_id=str(org.id),
            kind=sub.kind,
        )
        apply_remote(sub, remote)
    else:
        sub.status = "trialing" if end else "active"
        sub.canceled_at = None
        if not end:
            sub.current_period_end = add_months(now, 12 if sub.plan == "annual" else 1)
            await _record_sim_invoice(session, sub, now)
    await session.flush()
    return sub


async def change_plan(session: AsyncSession, org_id: uuid.UUID, plan: str) -> Subscription:
    if plan not in PLANS:
        raise AppError("Plano inválido.", code="invalid_plan")
    sub = await get_subscription(session, org_id)
    if sub is None:
        raise NotFound("Não há assinatura.", code="no_subscription")
    if _live() and sub.stripe_subscription_id and sub.status != "canceled":
        await gateway.change_price(sub.stripe_subscription_id, _price_id(plan))
    sub.plan = plan
    await session.flush()
    return sub


async def portal_url(session: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    sub = await get_subscription(session, org_id)
    if sub is None or not sub.stripe_customer_id:
        raise NotFound("Não há assinatura.", code="no_subscription")
    back = get_settings().frontend_url.rstrip("/") + "/app/assinatura"
    if not _live():
        return {"simulated": True, "url": back}
    return {"simulated": False, "url": await gateway.portal(sub.stripe_customer_id, back)}


async def invoices(session: AsyncSession, org_id: uuid.UUID) -> list[Invoice]:
    return list(
        (
            await session.execute(
                select(Invoice).where(Invoice.org_id == org_id).order_by(Invoice.created_at.desc())
            )
        ).scalars()
    )


# ------------------------------------------------------------------ one-off purchases

PURCHASE_HOOKS: dict[str, Any] = {}


def on_purchase_paid(kind: str):  # noqa: ANN201
    """Modules register what happens when a purchase of their kind is paid (boost, mentorship,
    event): ``@on_purchase_paid("boost") async def activate(session, purchase): ...``"""

    def deco(fn: Any) -> Any:
        PURCHASE_HOOKS[kind] = fn
        return fn

    return deco


async def _run_hook(session: AsyncSession, purchase: Purchase) -> None:
    import importlib

    module = {"boost": "boosts", "mentorship": "mentorship", "event": "events"}.get(purchase.kind)
    if module:
        try:
            importlib.import_module(f"app.modules.{module}.service")
        except ModuleNotFoundError:
            pass
    hook = PURCHASE_HOOKS.get(purchase.kind)
    if hook is not None:
        await hook(session, purchase)


async def checkout(
    session: AsyncSession,
    org: Organization,
    user: User,
    *,
    kind: str,
    ref: str,
    name: str,
    amount_cents: int,
    return_path: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sub = await get_subscription(session, org.id) or Subscription(org_id=org.id)
    if sub.id is None:
        session.add(sub)
    await _ensure_customer(session, org, user, sub)
    purchase = Purchase(
        org_id=org.id, kind=kind, ref=ref, amount_cents=amount_cents, data=data or {}
    )
    session.add(purchase)
    await session.flush()
    base = get_settings().frontend_url.rstrip("/")
    if not _live():
        purchase.status = "paid"
        purchase.paid_at = datetime.now(UTC)
        purchase.stripe_session_id = f"sim_cs_{secrets.token_hex(6)}"
        await _run_hook(session, purchase)
        return {
            "simulated": True,
            "url": f"{base}{return_path}?pago=1",
            "purchase_id": str(purchase.id),
        }
    cs = await gateway.checkout_payment(
        customer_id=sub.stripe_customer_id,
        name=name,
        amount_cents=amount_cents,
        success_url=f"{base}{return_path}?pago=1",
        cancel_url=f"{base}{return_path}",
        metadata={"purchase_id": str(purchase.id), "kind": kind, "org_id": str(org.id)},
    )
    purchase.stripe_session_id = cs["id"]
    return {"simulated": False, "url": cs["url"], "purchase_id": str(purchase.id)}


# ------------------------------------------------------------------ webhook


async def handle_webhook(session: AsyncSession, payload: bytes, signature: str) -> str:
    try:
        event = gateway.construct_event(payload, signature)
    except Exception as exc:  # noqa: BLE001 - stripe raises several types
        raise AppError("Assinatura do webhook inválida.", code="bad_signature") from exc
    return await process_event(session, dict(event))


async def process_event(session: AsyncSession, event: dict[str, Any]) -> str:
    """Idempotent by event id. Returns "duplicate" | "processed" | "ignored"."""
    if await session.get(StripeEvent, event["id"]) is not None:
        return "duplicate"
    row = StripeEvent(
        id=event["id"], type=event["type"], payload=event, received_at=datetime.now(UTC)
    )
    session.add(row)
    await session.flush()
    obj = event["data"]["object"]
    etype = event["type"]
    try:
        if etype.startswith("customer.subscription."):
            await _sync_subscription(session, obj, event_created=_ts(event.get("created")))
        elif etype == "invoice.paid":
            await _invoice_paid(session, obj)
        elif etype == "invoice.payment_failed":
            await _invoice_failed(session, obj)
        elif etype == "checkout.session.completed":
            await _checkout_completed(session, obj)
        else:
            row.processed_at = datetime.now(UTC)
            return "ignored"
    except Exception as exc:
        row.error = str(exc)[:500]
        raise
    row.processed_at = datetime.now(UTC)
    return "processed"


async def _sub_by_remote(session: AsyncSession, obj: dict[str, Any]) -> Subscription | None:
    sub_id = obj.get("subscription") if obj.get("object") == "invoice" else obj.get("id")
    if sub_id:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
            )
        ).scalar_one_or_none()
        if sub:
            return sub
    org_id = (obj.get("metadata") or {}).get("org_id")
    if org_id:
        return await get_subscription(session, uuid.UUID(org_id))
    return None


async def _sync_subscription(
    session: AsyncSession, obj: dict[str, Any], *, event_created: datetime | None
) -> None:
    sub = await _sub_by_remote(session, obj)
    if sub is None:
        return
    # out-of-order delivery: an event older than our last sync is re-read from Stripe
    if event_created and sub.last_synced_at and event_created < sub.last_synced_at and _live():
        obj = dict(await gateway.retrieve_subscription(obj["id"]))
    before = sub.status
    apply_remote(sub, obj)
    if before != "canceled" and sub.status == "canceled":
        await _notify_billing(
            session, sub, "billing.canceled", {"detalhe": "Nenhuma nova cobrança será feita."}
        )


async def _invoice_paid(session: AsyncSession, obj: dict[str, Any]) -> None:
    sub = await _sub_by_remote(session, obj)
    if sub is None or not obj.get("amount_paid"):
        return
    inv = (
        await session.execute(select(Invoice).where(Invoice.stripe_invoice_id == obj["id"]))
    ).scalar_one_or_none()
    if inv is None:
        inv = Invoice(org_id=sub.org_id, stripe_invoice_id=obj["id"])
        session.add(inv)
    inv.amount_cents = int(obj.get("amount_paid") or 0)
    inv.status = "paid"
    inv.paid_at = _ts((obj.get("status_transitions") or {}).get("paid_at")) or datetime.now(UTC)
    inv.hosted_url = str(obj.get("hosted_invoice_url") or "")
    inv.description = "Assinatura VIP Network"
    await session.flush()
    await _notify_billing(
        session, sub, "billing.payment_succeeded", {"valor": brl(inv.amount_cents)}
    )


async def _invoice_failed(session: AsyncSession, obj: dict[str, Any]) -> None:
    sub = await _sub_by_remote(session, obj)
    if sub is None:
        return
    sub.status = "past_due"
    await _notify_billing(
        session,
        sub,
        "billing.payment_failed",
        {"valor": brl(int(obj.get("amount_due") or 0)), "cartao_final": sub.card_last4},
    )


async def _checkout_completed(session: AsyncSession, obj: dict[str, Any]) -> None:
    purchase_id = (obj.get("metadata") or {}).get("purchase_id")
    if not purchase_id:
        return
    purchase = await session.get(Purchase, uuid.UUID(purchase_id))
    if purchase is None or purchase.status == "paid":
        return
    purchase.status = "paid"
    purchase.paid_at = datetime.now(UTC)
    await _run_hook(session, purchase)


async def _notify_billing(
    session: AsyncSession, sub: Subscription, key: str, variables: dict[str, Any]
) -> None:
    from app.modules.notifications import service as notifications

    titles = {
        "billing.payment_succeeded": "Pagamento confirmado",
        "billing.payment_failed": "Pagamento recusado: atualize o cartão",
        "billing.canceled": "Assinatura cancelada",
        "billing.trial_ending": "Seu teste grátis termina em 2 dias",
        "billing.trial_started": "Bem-vindo à VIP Network",
        "vip.expiring": "Seu Plano VIP vai vencer",
        "vip.expired": "Seu Plano VIP venceu",
    }
    await notifications.notify(
        session,
        sub.org_id,
        kind=key,
        title=titles.get(key, "Assinatura"),
        link="/app/assinatura",
        departments=("diretoria", "financeiro"),
        email_vars=variables,
    )


# ------------------------------------------------------------------ background


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    from zoneinfo import ZoneInfo

    return dt.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y")


async def tick(session: AsyncSession) -> None:
    """Trial and VIP reminders; in simulated mode, also the end of trials (Stripe's clock)."""
    now = datetime.now(UTC)
    subs = (
        (
            await session.execute(
                select(Subscription).where(Subscription.status.in_(("trialing", "active")))
            )
        )
        .scalars()
        .all()
    )
    for sub in subs:
        if sub.kind == "standard" and sub.status == "trialing" and sub.trial_end:
            left = sub.trial_end - now
            if timedelta(0) < left <= timedelta(hours=48) and not await _reminded(
                session, sub, "trial_ending"
            ):
                await _notify_billing(
                    session,
                    sub,
                    "billing.trial_ending",
                    {
                        "dias": "2",
                        "valor": brl(PRICES_CENTS[sub.plan]),
                        "data_cobranca": _fmt(sub.trial_end),
                        "cartao_final": sub.card_last4,
                    },
                )
            if left <= timedelta(0) and not _live():
                sub.status = "active"
                sub.current_period_end = add_months(
                    sub.trial_end, 12 if sub.plan == "annual" else 1
                )
                inv = await _record_sim_invoice(session, sub, now)
                await _notify_billing(
                    session, sub, "billing.payment_succeeded", {"valor": brl(inv.amount_cents)}
                )
        if sub.kind == "vip" and sub.vip_until:
            days = (sub.vip_until - now).days
            after = (
                "Depois dessa data, a renovação segue as regras da VIP Network. Nada é cobrado "
                "automaticamente."
                if sub.vip_after == "invite_only"
                else f"Depois dessa data, a assinatura segue no plano {'anual' if sub.plan == 'annual' else 'mensal'}, "
                f"{brl(PRICES_CENTS[sub.plan])}, no cartão final {sub.card_last4}."
            )
            for mark in (30, 15, 3):
                if days == mark - 1 and not await _reminded(session, sub, f"vip_{mark}"):
                    await _notify_billing(
                        session,
                        sub,
                        "vip.expiring",
                        {
                            "dias": str(mark),
                            "data_vencimento": _fmt(sub.vip_until),
                            "depois_do_vencimento": after,
                        },
                    )
            if sub.vip_until <= now and not await _reminded(session, sub, "vip_expired"):
                await _notify_billing(session, sub, "vip.expired", {"depois_do_vencimento": after})
                if not _live():
                    if sub.vip_after == "invite_only":
                        sub.status = "canceled"
                        sub.canceled_at = now
                    else:
                        sub.status = "active"
                        sub.current_period_end = add_months(now, 12 if sub.plan == "annual" else 1)
                        await _record_sim_invoice(session, sub, now)


async def _reminded(session: AsyncSession, sub: Subscription, mark: str) -> bool:
    """Each reminder once: kept as an audit row (action billing.reminder, target mark)."""
    from app.modules.audit.models import AuditLog

    key = f"{sub.id}:{mark}"
    exists = (
        await session.execute(
            select(AuditLog.id).where(
                AuditLog.action == "billing.reminder", AuditLog.target_id == key
            )
        )
    ).first()
    if exists:
        return True
    session.add(
        AuditLog(
            org_id=sub.org_id, action="billing.reminder", target_type="subscription", target_id=key
        )
    )
    return False


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
            log.exception("billing tick failed")
        await asyncio.sleep(300)

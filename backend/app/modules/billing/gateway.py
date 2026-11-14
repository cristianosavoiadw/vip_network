"""Thin async wrappers over the Stripe SDK (sync calls in a thread). Everything VIP Network
creates is tagged ``metadata.app = vip_network`` so a shared Stripe account stays readable."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import stripe

from app.core.config import get_settings

META = {"app": "vip_network"}


def _client() -> None:
    stripe.api_key = get_settings().stripe_secret_key


async def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    _client()
    return await asyncio.to_thread(fn, *args, **kwargs)


async def create_customer(*, name: str, email: str, cnpj: str, org_id: str) -> Any:
    return await _call(
        stripe.Customer.create,
        name=name,
        email=email,
        metadata={**META, "org_id": org_id, "cnpj": cnpj},
    )


async def setup_intent(customer_id: str) -> Any:
    return await _call(
        stripe.SetupIntent.create,
        customer=customer_id,
        usage="off_session",
        payment_method_types=["card"],
        metadata=META,
    )


async def attach_default_card(customer_id: str, payment_method_id: str) -> Any:
    pm = await _call(stripe.PaymentMethod.attach, payment_method_id, customer=customer_id)
    await _call(
        stripe.Customer.modify,
        customer_id,
        invoice_settings={"default_payment_method": payment_method_id},
    )
    return pm


async def create_subscription(
    *,
    customer_id: str,
    price_id: str,
    trial_end: datetime | None,
    cancel_at: datetime | None,
    org_id: str,
    kind: str,
) -> Any:
    kwargs: dict[str, Any] = {
        "customer": customer_id,
        "items": [{"price": price_id}],
        "metadata": {**META, "org_id": org_id, "kind": kind},
        "payment_behavior": "default_incomplete" if trial_end is None else "allow_incomplete",
        "expand": ["latest_invoice"],
    }
    if trial_end is not None:
        kwargs["trial_end"] = int(trial_end.timestamp())
        # no card charge attempt can happen before the trial ends
        kwargs["trial_settings"] = {"end_behavior": {"missing_payment_method": "cancel"}}
    if cancel_at is not None:
        kwargs["cancel_at"] = int(cancel_at.timestamp())
    return await _call(stripe.Subscription.create, **kwargs)


async def retrieve_subscription(sub_id: str) -> Any:
    return await _call(stripe.Subscription.retrieve, sub_id)


async def cancel_now(sub_id: str) -> Any:
    return await _call(stripe.Subscription.cancel, sub_id)


async def cancel_at_period_end(sub_id: str, value: bool) -> Any:
    return await _call(stripe.Subscription.modify, sub_id, cancel_at_period_end=value)


async def change_price(sub_id: str, price_id: str) -> Any:
    sub = await retrieve_subscription(sub_id)
    item_id = sub["items"]["data"][0]["id"]
    return await _call(
        stripe.Subscription.modify,
        sub_id,
        items=[{"id": item_id, "price": price_id}],
        proration_behavior="none",
    )


async def portal(customer_id: str, return_url: str) -> str:
    s = await _call(
        stripe.billing_portal.Session.create, customer=customer_id, return_url=return_url
    )
    return str(s["url"])


async def checkout_payment(
    *,
    customer_id: str,
    name: str,
    amount_cents: int,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
) -> Any:
    return await _call(
        stripe.checkout.Session.create,
        mode="payment",
        customer=customer_id,
        line_items=[
            {
                "price_data": {
                    "currency": "brl",
                    "unit_amount": amount_cents,
                    "product_data": {"name": name},
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={**META, **metadata},
        payment_intent_data={"metadata": {**META, **metadata}},
    )


def construct_event(payload: bytes, signature: str) -> Any:
    return stripe.Webhook.construct_event(payload, signature, get_settings().stripe_webhook_secret)


async def list_invoices(customer_id: str, limit: int = 24) -> Any:
    return await _call(stripe.Invoice.list, customer=customer_id, limit=limit)

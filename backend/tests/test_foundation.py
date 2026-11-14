"""Phase 1: sign-up by CNPJ, sessions, trial billing, VIP invites, access modes, departments."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.modules.billing import service as billing
from app.modules.billing.models import Subscription
from app.modules.invites.models import Invite
from app.modules.organizations.models import Organization
from tests.conftest import PASSWORD, World


async def _sub(org_id: str) -> Subscription:
    async with SessionLocal() as s:
        return (
            await s.execute(select(Subscription).where(Subscription.org_id == org_id))
        ).scalar_one()


# ------------------------------------------------------------------ sign-up and session


async def test_register_creates_pending_company_with_departments(world: World) -> None:
    c = await world.register()
    r = await world.client.get("/api/v1/auth/me", headers=c.h)
    me = r.json()
    assert me["org"]["status"] == "pending"
    assert me["org"]["official"]["cnae_description"].startswith("Fabricação")
    assert me["user"]["is_org_owner"] is True
    assert "team" in me["areas"] and "billing" in me["areas"]
    team = (await world.client.get("/api/v1/team", headers=c.h)).json()
    assert {d["slug"] for d in team["departments"]} == {
        "diretoria",
        "comercial",
        "compras",
        "financeiro",
        "rh",
    }


async def test_app_routes_blocked_until_onboarding_done(world: World) -> None:
    c = await world.register()
    r = await world.client.get("/api/v1/invites", headers=c.h)
    assert r.status_code == 403 and r.json()["code"] == "onboarding"


async def test_existing_cnpj_goes_to_access_request(world: World) -> None:
    c = await world.active_company()
    r = await world.client.post(
        "/api/v1/auth/register",
        json={
            "cnpj": c.cnpj,
            "full_name": "Outra Pessoa",
            "email": world.email(),
            "password": PASSWORD,
            "cnpj_relation": "autorizado",
        },
    )
    assert r.status_code == 409 and r.json()["code"] == "cnpj_registered"
    look = (await world.client.get(f"/api/v1/organizations/cnpj/{c.cnpj}/lookup")).json()
    assert look["exists"] is True and look["official"] is None
    r = await world.client.post(
        "/api/v1/organizations/access-requests",
        json={"cnpj": c.cnpj, "full_name": "Outra Pessoa", "email": world.email()},
    )
    assert r.status_code == 200
    team = (await world.client.get("/api/v1/team", headers=c.h)).json()
    assert len(team["access_requests"]) == 1


async def test_login_refresh_rotates_and_logout(world: World) -> None:
    c = await world.register()
    r = await world.client.post("/api/v1/auth/login", json={"email": c.email, "password": PASSWORD})
    assert r.status_code == 200
    r2 = await world.client.post("/api/v1/auth/refresh")
    assert r2.status_code == 200 and r2.json()["access_token"]
    await world.client.post("/api/v1/auth/logout")
    assert (await world.client.post("/api/v1/auth/refresh")).status_code == 401
    bad = await world.client.post(
        "/api/v1/auth/login", json={"email": c.email, "password": "errada123"}
    )
    assert bad.status_code == 401


# ------------------------------------------------------------------ trial billing


async def test_trial_ends_exactly_168_hours_after_creation(world: World) -> None:
    c = await world.register()
    q = (await world.client.get("/api/v1/billing/quote?plan=monthly", headers=c.h)).json()
    assert q["today_cents"] == 0 and q["amount_cents"] == 25_000
    before = datetime.now(UTC)
    r = await world.client.post("/api/v1/billing/subscribe", json={"plan": "monthly"}, headers=c.h)
    assert r.status_code == 200
    sub = await _sub(c.org_id)
    assert sub.status == "trialing"
    assert sub.trial_end - sub.trial_start == timedelta(hours=168)
    assert sub.trial_start >= before - timedelta(seconds=1)


async def test_one_trial_per_cnpj(world: World) -> None:
    c = await world.active_company()
    async with SessionLocal() as s:  # the company leaves and comes back with a new account
        org = await s.get(Organization, c.org_id)
        await s.delete(org)
        await s.commit()
    c2 = await world.register(cnpj=c.cnpj)
    q = (await world.client.get("/api/v1/billing/quote?plan=monthly", headers=c2.h)).json()
    assert q["trial"] is False and q["today_cents"] == 25_000
    await world.client.post("/api/v1/billing/subscribe", json={"plan": "monthly"}, headers=c2.h)
    sub = await _sub(c2.org_id)
    assert sub.status == "active" and sub.trial_end is None


async def test_cancel_during_trial_blocks_first_charge_and_keeps_access(world: World) -> None:
    c = await world.active_company()
    r = await world.client.post("/api/v1/billing/cancel", headers=c.h)
    assert r.status_code == 200 and r.json()["status"] == "canceled"
    sub = await _sub(c.org_id)
    assert sub.status == "canceled"
    # simulated clock: the end of the trial must not create a charge for a canceled sub
    async with SessionLocal() as s:
        row = (await s.execute(select(Subscription).where(Subscription.id == sub.id))).scalar_one()
        row.trial_end = datetime.now(UTC) - timedelta(minutes=1)
        await billing.tick(s)
        await s.commit()
    assert (await world.client.get("/api/v1/billing/invoices", headers=c.h)).json() == []
    # still entitled? no: trial over and canceled
    assert (await world.client.get("/api/v1/invites", headers=c.h)).status_code == 402


async def test_trial_end_charges_in_simulated_mode(world: World) -> None:
    c = await world.active_company(plan="annual")
    async with SessionLocal() as s:
        row = (
            await s.execute(select(Subscription).where(Subscription.org_id == c.org_id))
        ).scalar_one()
        row.trial_end = datetime.now(UTC) - timedelta(minutes=1)
        await billing.tick(s)
        await s.commit()
    invoices = (await world.client.get("/api/v1/billing/invoices", headers=c.h)).json()
    assert len(invoices) == 1 and invoices[0]["amount_cents"] == 250_000
    assert (await _sub(c.org_id)).status == "active"


async def test_webhook_is_idempotent(world: World) -> None:
    c = await world.active_company()
    sub = await _sub(c.org_id)
    event = {
        "id": f"evt_test_{c.cnpj}",
        "type": "customer.subscription.updated",
        "created": int(datetime.now(UTC).timestamp()),
        "data": {
            "object": {
                "id": sub.stripe_subscription_id,
                "object": "subscription",
                "status": "past_due",
                "metadata": {"org_id": c.org_id},
            }
        },
    }
    async with SessionLocal() as s:
        assert await billing.process_event(s, event) == "processed"
        await s.commit()
    async with SessionLocal() as s:
        assert await billing.process_event(s, event) == "duplicate"
        from app.modules.billing.models import StripeEvent

        await s.delete(await s.get(StripeEvent, event["id"]))
        await s.commit()
    assert (await _sub(c.org_id)).status == "past_due"


# ------------------------------------------------------------------ access modes and invites


async def test_invite_only_mode_requires_invite(world: World) -> None:
    await world.set_access(mode="invite")
    r = await world.client.post(
        "/api/v1/auth/register",
        json={
            "cnpj": world.cnpj(),
            "full_name": "Sem Convite",
            "email": world.email(),
            "password": PASSWORD,
            "cnpj_relation": "socio",
        },
    )
    assert r.status_code == 403 and r.json()["code"] == "invite_required"
    assert (await world.client.get("/api/v1/invites/access")).json()["mode"] == "invite"


async def test_invite_flow_vip_plan_and_three_invites(world: World) -> None:
    await world.set_access(mode="both", vip_months=6, invites_per_member=3, who_invites="invitees")
    host = await world.active_company()
    # a subscriber does not invite when who_invites = invitees
    r = await world.client.post(
        "/api/v1/invites",
        headers=host.h,
        json={
            "first_name": "Ana",
            "last_name": "Souza",
            "company_name": "Empresa X",
            "email": world.email(),
        },
    )
    assert r.status_code == 403 and r.json()["code"] == "not_eligible"
    # the team issues an invite (no limit)
    target = world.cnpj()
    guest_email = world.email()
    async with SessionLocal() as s:
        from app.modules.invites import service as invites

        inv = await invites.create(
            s,
            org=None,
            user=None,
            first_name="Paula",
            last_name="Reis",
            company_name="Convidada",
            email=guest_email,
            by_staff=True,
        )
        await s.commit()
        code = inv.code
    check = (await world.client.get(f"/api/v1/invites/check/{code}")).json()
    assert check["vip_months"] == 6 and check["invites_per_member"] == 3
    assert check["first_name"] == "Paula" and check["email"] == guest_email
    # the invite is bound to its e-mail (no CNPJ asked)
    r = await world.client.post(
        "/api/v1/auth/register",
        json={
            "cnpj": world.cnpj(),
            "full_name": "Errada",
            "email": world.email(),
            "password": PASSWORD,
            "cnpj_relation": "socio",
            "invite_code": code,
        },
    )
    assert r.json()["code"] == "invite_other_email"
    guest = await world.register(invite_code=code, cnpj=target, email=guest_email)
    q = (await world.client.get("/api/v1/billing/quote?plan=monthly", headers=guest.h)).json()
    assert q["vip"] is True and q["after"] == "then_charge"
    await world.client.post("/api/v1/billing/subscribe", json={"plan": "monthly"}, headers=guest.h)
    await world.client.post("/api/v1/organizations/me/onboarding/complete", headers=guest.h)
    sub = await _sub(guest.org_id)
    assert sub.kind == "vip" and sub.vip_after == "then_charge"
    assert 180 <= (sub.vip_until - sub.trial_start).days <= 184
    # the guest has 3 invites; the 4th is refused; a revoked one comes back
    mine = (await world.client.get("/api/v1/invites", headers=guest.h)).json()
    assert mine["remaining"] == 3
    ids = []
    for _ in range(3):
        r = await world.client.post(
            "/api/v1/invites",
            headers=guest.h,
            json={
                "first_name": "Ana",
                "last_name": "Souza",
                "company_name": "Indicada",
                "email": world.email(),
            },
        )
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    r = await world.client.post(
        "/api/v1/invites",
        headers=guest.h,
        json={
            "first_name": "Ana",
            "last_name": "Souza",
            "company_name": "Quarta",
            "email": world.email(),
        },
    )
    assert r.json()["code"] == "no_invites_left"
    await world.client.post(f"/api/v1/invites/{ids[0]}/revoke", headers=guest.h)
    assert (await world.client.get("/api/v1/invites", headers=guest.h)).json()["remaining"] == 1
    async with SessionLocal() as s:
        accepted = (await s.execute(select(Invite).where(Invite.code == code))).scalar_one()
        assert accepted.status == "accepted"


async def test_invite_only_vip_is_never_charged(world: World) -> None:
    await world.set_access(mode="invite")
    target = world.cnpj()
    guest_email = world.email()
    async with SessionLocal() as s:
        from app.modules.invites import service as invites

        inv = await invites.create(
            s,
            org=None,
            user=None,
            first_name="Clara",
            last_name="Lima",
            company_name="Clube",
            email=guest_email,
            by_staff=True,
        )
        await s.commit()
    guest = await world.register(invite_code=inv.code, cnpj=target, email=guest_email)
    q = (await world.client.get("/api/v1/billing/quote?plan=monthly", headers=guest.h)).json()
    assert q["vip_months"] == 12 and q["first_charge_at"] is None
    await world.client.post("/api/v1/billing/subscribe", json={"plan": "monthly"}, headers=guest.h)
    async with SessionLocal() as s:
        row = (
            await s.execute(select(Subscription).where(Subscription.org_id == guest.org_id))
        ).scalar_one()
        assert row.vip_after == "invite_only"
        row.vip_until = datetime.now(UTC) - timedelta(minutes=1)
        await billing.tick(s)
        await s.commit()
    assert (await world.client.get("/api/v1/billing/invoices", headers=guest.h)).json() == []
    assert (await _sub(guest.org_id)).status == "canceled"


async def test_paid_mode_turns_invites_off(world: World) -> None:
    await world.set_access(mode="paid")
    r = await world.client.get("/api/v1/invites/check/VIP-XXXX-XXXX")
    assert r.status_code == 403 and r.json()["code"] == "invites_off"


# ------------------------------------------------------------------ departments


async def test_department_permissions_are_enforced(world: World) -> None:
    c = await world.active_company()
    email = world.email()
    r = await world.client.post(
        "/api/v1/team/members",
        headers=c.h,
        json={"email": email, "full_name": "Luiza Financeiro", "departments": ["financeiro"]},
    )
    assert r.status_code == 200 and r.json()["status"] == "pending"
    from app.modules.auth import service as auth

    async with SessionLocal() as s:
        user = await auth.get_by_email(s, email)
        token = await auth.issue_link(s, user, "activate")
        await s.commit()
    r = await world.client.post(
        f"/api/v1/auth/activate/{token}", json={"password": PASSWORD, "password_confirm": PASSWORD}
    )
    assert r.status_code == 200
    me = r.json()
    assert "billing" in me["areas"] and "team" not in me["areas"] and "purchases" not in me["areas"]
    h = {"Authorization": f"Bearer {me['access_token']}"}
    assert (await world.client.get("/api/v1/team", headers=h)).status_code == 403
    assert (await world.client.get("/api/v1/billing/subscription", headers=h)).status_code == 200
    # the link is spent
    again = await world.client.post(
        f"/api/v1/auth/activate/{token}", json={"password": PASSWORD, "password_confirm": PASSWORD}
    )
    assert again.status_code == 404

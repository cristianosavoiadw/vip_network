"""Team panel: admin roles, least privilege, subscription math, e-mail admin, demo data."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.modules.admin import demo
from app.modules.analytics import service as metrics
from app.modules.auth import service as auth_service
from app.modules.billing.models import Subscription
from app.modules.catalog.models import PurchaseNeed
from app.modules.mail import service as mail_service
from app.modules.mail.models import EmailCampaign, EmailMessage, EmailSuppression, EmailTemplate
from app.modules.organizations.models import Organization
from tests.conftest import PASSWORD, World


async def _admin(world: World, role: str = "owner") -> dict[str, str]:
    email = world.email()
    async with SessionLocal() as s:
        await auth_service.create_user(
            s, email=email, password=PASSWORD, kind="admin", admin_role=role, full_name="Equipe"
        )
        await s.commit()
    r = await world.client.post(
        "/api/v1/auth/admin/login", json={"email": email, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ------------------------------------------------------------------ access


async def test_company_user_gets_403_on_admin(world: World) -> None:
    c = await world.active_company()
    for path in (
        "/api/v1/admin/overview",
        "/api/v1/admin/mail/triggers",
        "/api/v1/admin/analytics",
    ):
        r = await world.client.get(path, headers=c.h)
        assert r.status_code == 403 and r.json()["code"] == "wrong_area", path


async def test_viewer_reads_but_cannot_write(world: World) -> None:
    c = await world.active_company()
    h = await _admin(world, "viewer")
    for path in (
        "/api/v1/admin/overview",
        "/api/v1/admin/subscriptions",
        "/api/v1/admin/orgs",
        f"/api/v1/admin/orgs/{c.org_id}",
        "/api/v1/admin/matchmaking",
        "/api/v1/admin/support",
        "/api/v1/admin/analytics",
        "/api/v1/admin/team",
        "/api/v1/admin/mail/overview",
        "/api/v1/admin/mail/config",
    ):
        r = await world.client.get(path, headers=h)
        assert r.status_code == 200, (path, r.text)
    r = await world.client.post(f"/api/v1/admin/orgs/{c.org_id}/verify", headers=h)
    assert r.status_code == 403 and r.json()["code"] == "read_only"


async def test_admin_suspends_and_reactivates_a_company(world: World) -> None:
    c = await world.active_company()
    h = await _admin(world)
    r = await world.client.post(f"/api/v1/admin/orgs/{c.org_id}/suspend", headers=h)
    assert r.status_code == 200 and r.json()["org"]["status"] == "suspended"
    assert (await world.client.get("/api/v1/invites", headers=c.h)).status_code == 403
    r = await world.client.post(f"/api/v1/admin/orgs/{c.org_id}/reactivate", headers=h)
    assert r.json()["org"]["status"] == "active"
    r = await world.client.post(f"/api/v1/admin/orgs/{c.org_id}/verify", headers=h)
    assert r.json()["org"]["verified"] is True


async def test_org_details_never_include_purchase_needs(world: World) -> None:
    c = await world.active_company()
    async with SessionLocal() as s:
        s.add(
            PurchaseNeed(
                org_id=uuid.UUID(c.org_id),
                name="Segredo de compra XYZ",
                current_supplier="Fornecedor Sigiloso",
                price_paid_cents=12_345,
            )
        )
        await s.commit()
    h = await _admin(world)
    r = await world.client.get(f"/api/v1/admin/orgs/{c.org_id}", headers=h)
    assert r.status_code == 200
    assert "Segredo de compra" not in r.text and "Fornecedor Sigiloso" not in r.text
    assert "12345" not in r.text
    body = r.json()
    assert body["members"] and body["subscription"]["status"] == "trialing"
    assert "purchase" not in " ".join(body["counts"])


async def test_only_owner_manages_owners(world: World) -> None:
    h_admin = await _admin(world, "admin")
    r = await world.client.post(
        "/api/v1/admin/team",
        json={"email": world.email(), "full_name": "Nova Dona", "admin_role": "owner"},
        headers=h_admin,
    )
    assert r.status_code == 403 and r.json()["code"] == "owner_only"
    h_owner = await _admin(world, "owner")
    email = world.email()
    r = await world.client.post(
        "/api/v1/admin/team",
        json={"email": email, "full_name": "Nova Pessoa", "admin_role": "viewer"},
        headers=h_owner,
    )
    assert r.status_code == 200 and r.json()["status"] == "pending"
    async with SessionLocal() as s:
        sent = (
            await s.execute(select(EmailMessage).where(EmailMessage.to_email == email))
        ).scalar_one()
        assert sent.template_key == "team.invite" and "/ativar/" in sent.variables["link"]
    r = await world.client.patch(
        f"/api/v1/admin/team/{r.json()['id']}", json={"blocked": True}, headers=h_admin
    )
    assert r.status_code == 200 and r.json()["status"] == "blocked"


# ------------------------------------------------------------------ subscription math


def test_mrr_excludes_trials_and_vip_free_period() -> None:
    now = datetime.now(UTC)
    later, earlier = now + timedelta(days=60), now - timedelta(days=5)
    subs = [
        Subscription(plan="monthly", kind="standard", status="active"),
        Subscription(plan="annual", kind="standard", status="active"),
        Subscription(plan="monthly", kind="standard", status="trialing"),
        Subscription(plan="monthly", kind="standard", status="past_due"),
        Subscription(plan="monthly", kind="vip", status="trialing", vip_until=later),
        Subscription(plan="annual", kind="vip", status="active", vip_until=later),
        # VIP period over, then_charge: a paying subscription like any other
        Subscription(plan="monthly", kind="vip", status="active", vip_until=earlier),
        Subscription(plan="monthly", kind="standard", status="canceled"),
    ]
    assert metrics.mrr_cents(subs, now) == round(25_000 + 250_000 / 12 + 25_000)


async def test_overview_and_analytics_shapes(world: World) -> None:
    await world.active_company()
    h = await _admin(world)
    ov = (await world.client.get("/api/v1/admin/overview", headers=h)).json()
    assert {"mrr_cents", "paying", "trialing", "vip", "churn"} <= set(ov["kpis"])
    assert [r["key"] for r in ov["today"]][0] == "new_orgs" and ov["today"][0]["today"] >= 1
    an = (await world.client.get("/api/v1/admin/analytics", headers=h)).json()
    assert an["arr_cents"] == an["mrr_cents"] * 12
    assert [s["key"] for s in an["revenue_month"]] == [
        "subscriptions",
        "boost",
        "mentorship",
        "event",
    ]
    assert len(an["cohorts"]) == 6 and "this_month" in an["main_indicator"]


# ------------------------------------------------------------------ e-mail admin


async def test_mandatory_trigger_cannot_be_switched_off(world: World) -> None:
    h = await _admin(world)
    r = await world.client.post(
        "/api/v1/admin/mail/triggers/auth.verify_email", json={"enabled": False}, headers=h
    )
    assert r.status_code == 409 and r.json()["code"] == "mandatory_trigger"
    groups = (await world.client.get("/api/v1/admin/mail/triggers", headers=h)).json()
    item = next(i for g in groups for i in g["items"] if i["key"] == "digest.weekly")
    before = item["enabled"]
    r = await world.client.post(
        "/api/v1/admin/mail/triggers/digest.weekly", json={"enabled": not before}, headers=h
    )
    assert r.status_code == 200 and r.json()["enabled"] is (not before)
    await world.client.post(
        "/api/v1/admin/mail/triggers/digest.weekly", json={"enabled": before}, headers=h
    )


async def test_system_template_is_never_deleted(world: World) -> None:
    h = await _admin(world)
    items = (await world.client.get("/api/v1/admin/mail/templates", headers=h)).json()
    system = next(t for t in items if t["kind"] == "system")
    r = await world.client.delete(f"/api/v1/admin/mail/templates/{system['id']}", headers=h)
    assert r.status_code == 409 and r.json()["code"] == "system_template"
    r = await world.client.post(
        "/api/v1/admin/mail/templates",
        json={"name": "Teste apagar", "subject": "Oi", "body_md": "Texto"},
        headers=h,
    )
    assert r.status_code == 200
    r = await world.client.delete(f"/api/v1/admin/mail/templates/{r.json()['id']}", headers=h)
    assert r.status_code == 200


async def test_preview_renders_variables_and_button(world: World) -> None:
    h = await _admin(world)
    r = await world.client.post(
        "/api/v1/admin/mail/preview",
        json={
            "subject": "Oi, {{ primeiro_nome }}",
            "preheader": "Da {{ empresa }}",
            "body_md": "Olá, **{{ primeiro_nome }}**.\n\n[Abrir a VIP Network]({{ link }})",
        },
        headers=h,
    )
    body = r.json()
    assert body["subject"] == "Oi, Marina" and body["preheader"] == "Da Andrade Embalagens"
    assert "<strong>Marina</strong>" in body["html"]
    assert "Abrir a VIP Network</a>" in body["html"] and "#C9A14A" in body["html"]
    assert "{{" not in body["html"]


async def test_campaign_queues_one_message_per_recipient_and_skips_suppressed(
    world: World,
) -> None:
    c1 = await world.active_company()
    c2 = await world.active_company()
    h = await _admin(world)
    async with SessionLocal() as s:
        await mail_service.suppress(s, c2.email, "unsubscribed")
        await s.commit()
    tpl = (
        await world.client.post(
            "/api/v1/admin/mail/templates",
            json={"name": "Teste campanha", "subject": "Oi {{ empresa }}", "body_md": "Olá."},
            headers=h,
        )
    ).json()
    name = f"Teste {uuid.uuid4().hex[:8]}"
    camp_id = tpl_id = None
    try:
        tpl_id = tpl["id"]
        r = await world.client.post(
            "/api/v1/admin/mail/campaigns",
            json={"name": name, "template_id": tpl_id, "audience": "trialing", "hourly_cap": 300},
            headers=h,
        )
        assert r.status_code == 200 and r.json()["status"] == "draft", r.text
        camp_id = r.json()["id"]
        assert r.json()["subject"] == "Oi {{ empresa }}"
        r = await world.client.post(f"/api/v1/admin/mail/campaigns/{camp_id}/start", headers=h)
        started = r.json()
        assert started["status"] == "sending"
        async with SessionLocal() as s:
            rows = (
                (
                    await s.execute(
                        select(EmailMessage).where(EmailMessage.campaign_id == uuid.UUID(camp_id))
                    )
                )
                .scalars()
                .all()
            )
        to = [m.to_email for m in rows]
        assert len(rows) == started["recipients"] == len(set(to))
        assert to.count(c1.email) == 1 and c2.email not in to
        r = await world.client.post(f"/api/v1/admin/mail/campaigns/{camp_id}/pause", headers=h)
        assert r.json()["status"] == "paused"
        # messages list masks the addresses
        r = await world.client.get(f"/api/v1/admin/mail/messages?q={name}", headers=h)
        items = r.json()["items"]
        assert items and all("***@" in i["to"] for i in items)
        assert c1.email not in r.text
        assert items[0]["origin"] == f"Campanha · {name}" and items[0]["status"] == "paused"
    finally:
        async with SessionLocal() as s:
            if camp_id:
                await s.execute(delete(EmailCampaign).where(EmailCampaign.id == uuid.UUID(camp_id)))
            if tpl_id:
                await s.execute(delete(EmailTemplate).where(EmailTemplate.id == uuid.UUID(tpl_id)))
            await s.execute(delete(EmailSuppression).where(EmailSuppression.email == c2.email))
            await s.commit()


def test_mask_email() -> None:
    from app.modules.mail.admin import mask_email

    assert mask_email("marina@andradeembalagens.com.br") == "ma***@andradeembalagens.com.br"


# ------------------------------------------------------------------ demo data


async def test_demo_run_is_idempotent() -> None:
    cnpjs = list(demo.DEMO_CNPJS.values())

    async def demo_orgs() -> int:
        async with SessionLocal() as s:
            q = select(func.count()).select_from(Organization).where(Organization.cnpj.in_(cnpjs))
            return int((await s.execute(q)).scalar_one())

    existed = await demo_orgs() > 0
    try:
        for _ in range(2):
            async with SessionLocal() as s:
                out = await demo.run(s)
                await s.commit()
            assert any(demo.ADMIN_EMAIL in line for line in out)
            assert await demo_orgs() == len(demo.ORGS)
        async with SessionLocal() as s:
            andrade = (
                await s.execute(
                    select(Organization).where(Organization.cnpj == demo.DEMO_CNPJS["andrade"])
                )
            ).scalar_one()
            sub = (
                await s.execute(select(Subscription).where(Subscription.org_id == andrade.id))
            ).scalar_one()
            assert sub.kind == "vip" and andrade.entry == "invite"
    finally:
        if not existed:
            async with SessionLocal() as s:
                await demo.clear(s)
                await s.commit()

"""Phase 3/4: recommendations and economy, Brilhar, events, mentorship, AI jobs, reports,
dashboard (scope §2.2, §2.3, §10.3, §14, §16–§19)."""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.modules.boosts import service as boosts
from app.modules.boosts.models import BoostCampaign
from app.modules.discovery.models import OrgBlock
from app.modules.events.models import Event
from app.modules.intelligence import engine
from app.modules.mentorship.models import Mentor, MentorshipPlan
from app.modules.notifications.models import Notification
from app.modules.weos import client, jobs
from app.modules.weos.models import AIJob
from tests.conftest import World
from tests.helpers_growth import add_need, add_offer, admin_headers, member_headers


def _cat() -> str:
    return f"Filme stretch {secrets.token_hex(4)}"


async def _kinds_for(org_id: str) -> list[str]:
    async with SessionLocal() as s:
        return list(
            (
                await s.execute(
                    select(Notification.kind).where(Notification.org_id == uuid.UUID(org_id))
                )
            ).scalars()
        )


# ------------------------------------------------------------------ economy and privacy


def test_economy_math_matches_the_scope_example() -> None:
    m = engine.economy_math(12_000, 9_500, 1_000)
    assert m["gross_cents"] == 2_500_000  # R$ 25.000/mês
    assert m["adjustment_cents"] == 120_000  # frete estimado R$ 1.200
    assert m["net_cents"] == 2_380_000  # R$ 23.800 líquido estimado
    assert m["estimate"] is True and m["pct"] == 21


async def test_economy_recommendation_and_seller_never_sees_buyer_price(world: World) -> None:
    buyer = await world.active_company()
    seller = await world.active_company()
    cat = _cat()
    await add_offer(
        seller,
        name="Filme stretch industrial 23 µm",
        category=cat,
        price_cents=9_500,
        unit="bobina",
    )
    await add_need(
        buyer,
        name="Filme stretch industrial",
        category=cat,
        price_paid_cents=12_000,
        volume_qty=1_000,
        unit="bobina",
        current_supplier="Fornecedor Secreto",
        visibility="published",
    )

    r = await world.client.post("/api/v1/intelligence/recommendations/refresh", headers=buyer.h)
    assert r.status_code == 200, r.text
    eco = [
        i for i in r.json()["items"] if i["kind"] == "economy" and i["org"]["id"] == seller.org_id
    ]
    assert len(eco) == 1
    d = eco[0]["data"]
    assert (d["gross_cents"], d["adjustment_cents"], d["net_cents"]) == (
        2_500_000,
        120_000,
        2_380_000,
    )
    assert eco[0]["estimate"] is True and "estimativa" in eco[0]["body"]

    # the dashboard of the buyer sums the open economy cards
    dash = (await world.client.get("/api/v1/dashboard?period=30", headers=buyer.h)).json()
    assert dash["kpis"]["potential_economy"]["value"] >= 2_380_000

    # the seller gets a buyer card from the PUBLISHED need, without price, volume or supplier
    r = await world.client.post("/api/v1/intelligence/recommendations/refresh", headers=seller.h)
    items = r.json()["items"]
    assert any(i["kind"] == "buyer" and i["org"]["id"] == buyer.org_id for i in items)
    assert not any(
        i["kind"] == "economy" for i in items if i["org"] and i["org"]["id"] == buyer.org_id
    )
    for path in ("/api/v1/intelligence/recommendations", "/api/v1/dashboard?period=30"):
        text = (await world.client.get(path, headers=seller.h)).text
        assert "12000" not in text and "120,00" not in text and "Fornecedor Secreto" not in text
        assert "price_paid" not in text and "paid_cents" not in text


async def test_private_need_never_reaches_other_companies(world: World) -> None:
    buyer = await world.active_company()
    seller = await world.active_company()
    cat = _cat()
    await add_offer(seller, name="Filme stretch", category=cat, price_cents=9_000)
    await add_need(
        buyer, name="Filme stretch", category=cat, price_paid_cents=12_000, volume_qty=10
    )
    r = await world.client.post("/api/v1/intelligence/recommendations/refresh", headers=seller.h)
    assert not any(
        i["kind"] == "buyer" and i["org"]["id"] == buyer.org_id for i in r.json()["items"]
    )


async def test_recommendations_skip_blocked_companies(world: World) -> None:
    buyer = await world.active_company()
    seller = await world.active_company()
    cat = _cat()
    await add_offer(seller, name="Filme stretch", category=cat, price_cents=9_000)
    await add_need(
        buyer, name="Filme stretch", category=cat, price_paid_cents=12_000, volume_qty=10
    )
    r = await world.client.post("/api/v1/intelligence/recommendations/refresh", headers=buyer.h)
    assert any(i["org"] and i["org"]["id"] == seller.org_id for i in r.json()["items"])

    async with SessionLocal() as s:
        s.add(
            OrgBlock(source_org_id=uuid.UUID(seller.org_id), target_org_id=uuid.UUID(buyer.org_id))
        )
        await s.commit()
    for h in (buyer.h, seller.h):
        r = await world.client.post("/api/v1/intelligence/recommendations/refresh", headers=h)
        ids = {i["org"]["id"] for i in r.json()["items"] if i["org"]}
        assert seller.org_id not in ids and buyer.org_id not in ids


async def test_dismissed_recommendation_stays_dismissed(world: World) -> None:
    buyer = await world.active_company()
    seller = await world.active_company()
    cat = _cat()
    await add_offer(seller, name="Filme stretch", category=cat, price_cents=9_000)
    await add_need(
        buyer, name="Filme stretch", category=cat, price_paid_cents=12_000, volume_qty=10
    )
    items = (
        await world.client.post("/api/v1/intelligence/recommendations/refresh", headers=buyer.h)
    ).json()["items"]
    eco = next(i for i in items if i["kind"] == "economy" and i["org"]["id"] == seller.org_id)
    r = await world.client.post(
        f"/api/v1/intelligence/recommendations/{eco['id']}/dismiss", headers=buyer.h
    )
    assert r.status_code == 200
    items = (
        await world.client.post("/api/v1/intelligence/recommendations/refresh", headers=buyer.h)
    ).json()["items"]
    assert not any(i["kind"] == "economy" and i["org"]["id"] == seller.org_id for i in items)
    # another company cannot dismiss it
    other = await world.active_company()
    r = await world.client.post(
        f"/api/v1/intelligence/recommendations/{eco['id']}/dismiss", headers=other.h
    )
    assert r.status_code == 404


# ------------------------------------------------------------------ Brilhar


async def test_boost_purchase_activates_and_stacks_after_active_campaign(world: World) -> None:
    c = await world.active_company()
    pk = (await world.client.get("/api/v1/boosts/packages", headers=c.h)).json()
    assert [(p["days"], p["price_cents"]) for p in pk["items"]] == [
        (1, 3_900),
        (10, 29_900),
        (30, 79_900),
    ]
    assert "não" in pk["disclaimer"] and "garante" in pk["disclaimer"]

    r = await world.client.post("/api/v1/boosts/checkout", json={"days": 1}, headers=c.h)
    assert r.status_code == 200 and r.json()["simulated"] is True
    r = await world.client.post("/api/v1/boosts/checkout", json={"days": 10}, headers=c.h)
    assert r.status_code == 200
    assert (
        await world.client.post("/api/v1/boosts/checkout", json={"days": 5}, headers=c.h)
    ).status_code == 400

    camps = (await world.client.get("/api/v1/boosts/campaigns", headers=c.h)).json()["items"]
    assert len(camps) == 2
    first = next(x for x in camps if x["days"] == 1)
    second = next(x for x in camps if x["days"] == 10)
    assert first["phase"] == "running" and second["phase"] == "scheduled"
    assert second["starts_at"] == first["ends_at"]
    assert "boost.purchased" in await _kinds_for(c.org_id)

    a = (await world.client.get("/api/v1/boosts/analytics", headers=c.h)).json()
    assert a["campaign"]["days"] == 1 and "garante" in a["disclaimer"]

    # the first one ends: finished + result notification
    async with SessionLocal() as s:
        camp = await s.get(BoostCampaign, uuid.UUID(first["id"]))
        camp.starts_at = datetime.now(UTC) - timedelta(days=2)
        camp.ends_at = datetime.now(UTC) - timedelta(minutes=1)
        await s.commit()
    async with SessionLocal() as s:
        assert await boosts.tick(s, org_id=uuid.UUID(c.org_id)) == 1
        await s.commit()
    camps = (await world.client.get("/api/v1/boosts/campaigns", headers=c.h)).json()["items"]
    assert next(x for x in camps if x["days"] == 1)["status"] == "finished"
    assert "boost.finished" in await _kinds_for(c.org_id)

    adm = (
        await world.client.get("/api/v1/admin/boosts", headers=await admin_headers(world))
    ).json()
    assert adm["packages_sold"] >= 2 and adm["revenue_month_cents"] >= 3_900 + 29_900


async def test_boost_buy_needs_sales_area(world: World) -> None:
    c = await world.active_company()
    fin = await member_headers(world, c, ["financeiro"])
    assert (await world.client.get("/api/v1/boosts/packages", headers=fin)).status_code == 200
    assert (
        await world.client.post("/api/v1/boosts/checkout", json={"days": 1}, headers=fin)
    ).status_code == 403


# ------------------------------------------------------------------ events


@pytest.fixture
async def event_ids() -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    yield ids
    async with SessionLocal() as s:
        await s.execute(delete(Event).where(Event.id.in_(ids)))
        await s.commit()


async def test_event_register_waitlist_and_cancel_promotes(
    world: World, event_ids: list[uuid.UUID]
) -> None:
    adm = await admin_headers(world)
    starts = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    r = await world.client.post(
        "/api/v1/admin/events",
        headers=adm,
        json={
            "title": "Jantar de Negócios VIP Teste",
            "city": "São Paulo",
            "state": "SP",
            "place": "Hotel",
            "starts_at": starts,
            "seats": 1,
        },
    )
    assert r.status_code == 200, r.text
    ev = r.json()
    event_ids.append(uuid.UUID(ev["id"]))
    a = await world.active_company()
    b = await world.active_company()

    r = await world.client.post(f"/api/v1/events/{ev['id']}/register", headers=a.h)
    assert r.status_code == 200 and r.json()["registration"]["status"] == "confirmed"
    assert r.json()["registration"]["checkin_token"]
    r = await world.client.post(f"/api/v1/events/{ev['id']}/register", headers=b.h)
    assert r.json()["registration"]["status"] == "waitlist"
    assert r.json()["registration"]["checkin_token"] is None
    assert (
        await world.client.post(f"/api/v1/events/{ev['id']}/register", headers=b.h)
    ).status_code == 409

    listed = (await world.client.get("/api/v1/events", headers=b.h)).json()["items"]
    mine = next(e for e in listed if e["id"] == ev["id"])
    assert mine["seats_left"] == 0 and mine["waitlist_open"] is True
    assert mine["my_registration"]["status"] == "waitlist"
    assert "high_potential_confirmed" in mine

    assert (
        await world.client.delete(f"/api/v1/events/{ev['id']}/registration", headers=a.h)
    ).status_code == 200
    listed = (await world.client.get("/api/v1/events", headers=b.h)).json()["items"]
    mine = next(e for e in listed if e["id"] == ev["id"])
    assert mine["my_registration"]["status"] == "confirmed"
    assert "event.waitlist_open" in await _kinds_for(b.org_id)
    assert "event.registered" in await _kinds_for(a.org_id)

    regs = (
        await world.client.get(f"/api/v1/admin/events/{ev['id']}/registrations", headers=adm)
    ).json()["items"]
    assert {r["status"] for r in regs} == {"canceled", "confirmed"}
    token = mine["my_registration"]["checkin_token"]
    r = await world.client.post(f"/api/v1/admin/events/checkin/{token}", headers=adm)
    assert r.status_code == 200 and r.json()["already"] is False
    assert (await world.client.post(f"/api/v1/admin/events/checkin/{token}", headers=adm)).json()[
        "already"
    ] is True
    # rating opens after the event
    assert (
        await world.client.post(
            f"/api/v1/events/{ev['id']}/rating", json={"rating": 5}, headers=b.h
        )
    ).status_code == 409


async def test_paid_event_goes_through_checkout(world: World, event_ids: list[uuid.UUID]) -> None:
    adm = await admin_headers(world)
    starts = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    ev = (
        await world.client.post(
            "/api/v1/admin/events",
            headers=adm,
            json={
                "title": "Rodada Paga",
                "kind": "rodada",
                "starts_at": starts,
                "seats": 10,
                "price_cents": 15_000,
            },
        )
    ).json()
    event_ids.append(uuid.UUID(ev["id"]))
    c = await world.active_company()
    r = await world.client.post(f"/api/v1/events/{ev['id']}/register", headers=c.h)
    assert r.status_code == 200, r.text
    assert r.json()["checkout"]["simulated"] is True
    assert r.json()["registration"]["status"] == "confirmed"


# ------------------------------------------------------------------ mentorship


async def test_mentorship_is_private_to_the_company(world: World) -> None:
    adm = await admin_headers(world)
    m = (
        await world.client.post(
            "/api/v1/admin/mentors", headers=adm, json={"name": "Mentora Teste", "is_lead": True}
        )
    ).json()
    try:
        a = await world.active_company()
        b = await world.active_company()
        r = await world.client.post("/api/v1/mentorship/checkout", headers=a.h)
        assert r.status_code == 200 and r.json()["simulated"] is True
        assert (
            await world.client.post("/api/v1/mentorship/checkout", headers=a.h)
        ).status_code == 409
        assert "mentorship.purchased" in await _kinds_for(a.org_id)

        mine = (await world.client.get("/api/v1/mentorship", headers=a.h)).json()
        assert mine["program"]["price_cents"] == 1_500_000
        plan = mine["plan"]
        assert plan["status"] == "active" and plan["ends_on"]
        async with SessionLocal() as s:
            p = await s.get(MentorshipPlan, uuid.UUID(plan["id"]))
            p.diagnosis = "Diagnostico confidencial XYZ"
            await s.commit()
        start = (datetime.now(UTC) + timedelta(days=3)).isoformat()
        r = await world.client.post(
            "/api/v1/mentorship/sessions",
            headers=a.h,
            json={"starts_at": start, "topic": "Diagnóstico"},
        )
        assert r.status_code == 200 and r.json()["status"] == "requested"
        assert (await world.client.get("/api/v1/mentorship", headers=a.h)).json()["plan"][
            "diagnosis"
        ] == "Diagnostico confidencial XYZ"

        other = (await world.client.get("/api/v1/mentorship", headers=b.h)).json()
        assert other["plan"] is None and "XYZ" not in json.dumps(other)
        assert (
            await world.client.post(
                "/api/v1/mentorship/sessions", headers=b.h, json={"starts_at": start, "topic": "x1"}
            )
        ).status_code == 409
        # a non-Diretoria colleague does not reach it
        com = await member_headers(world, a, ["comercial"])
        assert (await world.client.get("/api/v1/mentorship", headers=com)).status_code == 403

        # the team sees the agenda only, never the content
        agenda = await world.client.get("/api/v1/admin/mentorship/agenda", headers=adm)
        plans = await world.client.get("/api/v1/admin/mentorship/plans", headers=adm)
        assert any(x["topic"] == "Diagnóstico" for x in agenda.json()["items"])
        for resp in (agenda, plans):
            assert "XYZ" not in resp.text and "diagnosis" not in resp.text
        sess_id = next(x["id"] for x in agenda.json()["items"] if x["plan_id"] == plan["id"])
        r = await world.client.patch(
            f"/api/v1/admin/mentorship/sessions/{sess_id}",
            headers=adm,
            json={"status": "scheduled"},
        )
        assert r.status_code == 200
        assert "mentorship.session" in await _kinds_for(a.org_id)
        # recommendations never read mentorship data
        recs = (
            await world.client.post("/api/v1/intelligence/recommendations/refresh", headers=a.h)
        ).text
        assert "XYZ" not in recs
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(Mentor).where(Mentor.id == uuid.UUID(m["id"])))
            await s.commit()


# ------------------------------------------------------------------ AI jobs


async def test_ai_jobs_are_deduplicated(world: World) -> None:
    c = await world.active_company()
    org = uuid.UUID(c.org_id)
    key = f"profile:{org}"
    async with SessionLocal() as s:
        j1 = await jobs.enqueue(s, "CompanyProfileAgent", org, {}, key)
        j2 = await jobs.enqueue(s, "CompanyProfileAgent", org, {}, key)
        assert j1.id == j2.id
        j1.status = "done"
        await s.flush()
        j3 = await jobs.enqueue(s, "CompanyProfileAgent", org, {}, key)
        assert j3.id != j1.id
        await s.commit()


async def test_ai_job_dead_letter_after_three_failures(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await world.active_company()
    calls = {"n": 0}

    async def boom(*_a: object, **_k: object) -> None:
        calls["n"] += 1
        raise client.WeOSError("WeOS respondeu 503.")

    monkeypatch.setattr(client, "configured", lambda: True)
    monkeypatch.setattr(client, "run_task", boom)
    async with SessionLocal() as s:
        job = await jobs.enqueue(s, "CompanyProfileAgent", uuid.UUID(c.org_id), {}, None)
        await s.commit()
        job_id = job.id
    for attempt in (1, 2, 3):
        async with SessionLocal() as s:
            job = await s.get(AIJob, job_id)
            await jobs.run_job(s, job)
            await s.commit()
            assert job.attempts == attempt
            if attempt < 3:
                assert job.status == "queued" and job.next_attempt_at > datetime.now(UTC)
            else:
                assert job.status == "dead" and "503" in job.error
    assert calls["n"] == 3

    adm = await admin_headers(world)
    overview = (await world.client.get("/api/v1/admin/agents", headers=adm)).json()
    row = next(a for a in overview["agents"] if a["agent"] == "CompanyProfileAgent")
    assert row["dead"] >= 1 and row["status"] == "with_failures"
    r = await world.client.post(
        "/api/v1/admin/agents/retry-dead", headers=adm, json={"agent": "CompanyProfileAgent"}
    )
    assert r.json()["requeued"] >= 1
    async with SessionLocal() as s:
        job = await s.get(AIJob, job_id)
        assert job.status == "queued" and job.attempts == 0


async def test_schema_validation_rejects_bad_answer() -> None:
    from app.modules.intelligence.service import REPORT_SCHEMA

    with pytest.raises(client.WeOSError):
        client.validate(
            {"sections": [{"key": "resumo", "title": "x", "confidence": "certeza"}]}, REPORT_SCHEMA
        )
    assert client.parse_json('```json\n{"a": 1}\n```') == {"a": 1}


async def test_market_report_generated_locally_reaches_ready(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client, "configured", lambda: False)
    c = await world.active_company()
    await add_offer(c, name="Bandeja térmica", category=_cat(), price_cents=100)
    r = await world.client.post("/api/v1/intelligence/reports", headers=c.h)
    assert r.status_code == 200 and r.json()["status"] == "queued"
    rep_id = r.json()["id"]
    assert (await world.client.post("/api/v1/intelligence/reports", headers=c.h)).json()[
        "id"
    ] == rep_id

    async with SessionLocal() as s:
        job = (
            await s.execute(
                select(AIJob).where(
                    AIJob.org_id == uuid.UUID(c.org_id), AIJob.agent == "MarketIntelligenceAgent"
                )
            )
        ).scalar_one()
        await jobs.run_job(s, job)
        await s.commit()
        assert job.status == "done" and job.model == jobs.LOCAL_MODEL and job.latency_ms is not None

    rep = (await world.client.get(f"/api/v1/intelligence/reports/{rep_id}", headers=c.h)).json()
    assert rep["status"] == "ready"
    keys = [s["key"] for s in rep["sections"]]
    assert keys[0] == "resumo" and "proximas_acoes" in keys and len(keys) == 10
    assert all(s["confidence"] in ("alta", "média", "baixa") for s in rep["sections"])
    trends = next(s for s in rep["sections"] if s["key"] == "tendencias")
    assert trends["confidence"] == "baixa" and "não fatos" in trends["body"]
    assert rep["sources"] and all(src["date"] for src in rep["sources"])
    assert "report.ready" in await _kinds_for(c.org_id)
    listed = (await world.client.get("/api/v1/intelligence/reports", headers=c.h)).json()["items"]
    assert listed[0]["id"] == rep_id
    other = await world.active_company()
    assert (
        await world.client.get(f"/api/v1/intelligence/reports/{rep_id}", headers=other.h)
    ).status_code == 404


# ------------------------------------------------------------------ dashboard


async def test_dashboard_follows_departments(world: World) -> None:
    c = await world.active_company()
    owner = (await world.client.get("/api/v1/dashboard?period=7", headers=c.h)).json()
    assert owner["mode"] == "commercial" and owner["period"] == 7
    for key in (
        "potential_economy",
        "matches_confirmed",
        "likes_received_buy",
        "likes_received_sell",
        "likes_sent_buy",
        "likes_sent_sell",
        "open_negotiations",
        "profile_visits",
        "unread_messages",
    ):
        assert key in owner["kpis"], key
    assert owner["billing"] is None

    fin = await member_headers(world, c, ["financeiro"])
    d = (await world.client.get("/api/v1/dashboard?period=30", headers=fin)).json()
    assert d["mode"] == "billing"
    assert (
        not {"potential_economy", "matches_confirmed", "likes_received_buy", "open_negotiations"}
        & d["kpis"].keys()
    )
    assert d["recommendations"] == []
    assert d["billing"]["subscription"]["status"] == "trialing"
    assert d["billing"]["next_charge"]["amount_cents"] == 25_000

    compras = await member_headers(world, c, ["compras"])
    d = (await world.client.get("/api/v1/dashboard", headers=compras)).json()
    assert "likes_received_sell" in d["kpis"] and "likes_received_buy" not in d["kpis"]
    assert "potential_economy" in d["kpis"] and d["billing"] is None

    comercial = await member_headers(world, c, ["comercial"])
    d = (await world.client.get("/api/v1/dashboard", headers=comercial)).json()
    assert "likes_received_buy" in d["kpis"] and "potential_economy" not in d["kpis"]
    assert all(r["kind"] not in ("economy", "supplier") for r in d["recommendations"])

    assert (await world.client.get("/api/v1/dashboard?period=12", headers=c.h)).status_code == 400

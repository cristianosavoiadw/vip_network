"""Phase 2: catalogs, discovery cards, likes with intent, reciprocity, matches, connections."""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.modules.boosts.models import BoostCampaign, OrgDayStat
from app.modules.matches.rules import reciprocity
from tests.conftest import World
from tests.helpers_network import (
    card_of,
    cards,
    everything_seen_by,
    like,
    member,
    need,
    notifications,
    offer,
)

# ------------------------------------------------------------------ rules (pure)

EXPECTED = {
    ("buy", "sell"): ("match", "commercial"),
    ("sell", "buy"): ("match", "commercial"),
    ("part", "part"): ("match", "partnership"),
    ("sell", "sell"): ("mutual", "mutual_sell"),
    ("buy", "buy"): ("mutual", "mutual_buy"),
}


@pytest.mark.parametrize(
    "mine,theirs", list(itertools.product(["buy", "sell", "part", "net"], repeat=2))
)
def test_reciprocity_table(mine: str, theirs: str) -> None:
    res = reciprocity(mine, theirs)
    kind, match_kind = EXPECTED.get((mine, theirs), ("mutual", "relationship"))
    assert (res.kind, res.match_kind) == (kind, match_kind)
    assert res.status == ("MATCH_CONFIRMED" if kind == "match" else "MUTUAL_INTEREST")


def test_reciprocity_without_their_like_is_unilateral() -> None:
    for intent in ("buy", "sell", "part", "net"):
        assert reciprocity(intent, None).kind == "unilateral"


# ------------------------------------------------------------------ catalog


async def test_catalog_crud_and_isolation(world: World) -> None:
    a = await world.active_company()
    b = await world.active_company()
    o = await offer(world, a, "Bandejas para hortifrúti", price_cents=38, price_on_request=False)
    n = await need(
        world,
        a,
        "Filme stretch industrial",
        price_paid_cents=12000,
        current_supplier="Fornecedor X",
    )
    assert n["visibility"] == "private"
    cats = (await world.client.get("/api/v1/catalog/categories", headers=a.h)).json()
    assert len(cats) >= 20 and "Embalagens" in cats
    # another company cannot touch them
    r = await world.client.patch(f"/api/v1/offers/{o['id']}", headers=b.h, json={"name": "Hack"})
    assert r.status_code == 404
    r = await world.client.delete(f"/api/v1/purchase-needs/{n['id']}", headers=b.h)
    assert r.status_code == 404
    assert (await world.client.get("/api/v1/purchase-needs", headers=b.h)).json() == []
    r = await world.client.patch(
        f"/api/v1/offers/{o['id']}", headers=a.h, json={"status": "paused"}
    )
    assert r.json()["status"] == "paused"
    assert (await world.client.delete(f"/api/v1/offers/{o['id']}", headers=a.h)).status_code == 200
    assert (await world.client.get("/api/v1/offers", headers=a.h)).json() == []


# ------------------------------------------------------------------ likes and matches


async def test_commercial_match_creates_connection_and_notifications(world: World) -> None:
    seller = await world.active_company()
    buyer = await world.active_company()
    await offer(world, seller, "Embalagens térmicas para congelados")

    r = await like(world, buyer, seller, "buy", ["Embalagens térmicas para congelados"])
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    assert res["kind"] == "unilateral" and res["match"] is None
    assert "verá que sua empresa tem interesse: compra" in res["message"]
    assert len(await notifications(seller.org_id, "like.buy_interest")) >= 1

    # the seller sees the received like without any match (Querem comprar de mim)
    page = (
        await world.client.get("/api/v1/likes?tab=compras&filter=received", headers=seller.h)
    ).json()
    group = next(g for g in page["groups"] if g["key"] == "querem_comprar")
    row = next(x for x in group["items"] if x["org"]["id"] == buyer.org_id)
    assert row["status"] == "waiting" and row["direction"] == "received" and row["intent"] == "buy"
    assert (await world.client.get("/api/v1/connections", headers=seller.h)).json() == []
    # their_like on the seller's card of the buyer
    card = card_of(await cards(world, seller), buyer)
    assert card is not None and card["their_like"]["intent"] == "buy"

    r = await like(world, seller, buyer, "sell", ["Embalagens térmicas para congelados"])
    res = r.json()["result"]
    assert res["kind"] == "match" and res["message"].startswith("É MATCH!")
    m = res["match"]
    assert m["kind"] == "commercial" and m["status"] == "MATCH_CONFIRMED"
    assert m["type_label"] == "Comercial: você vende" and m["origin"] == "MUTUAL_LIKE"

    for c, other in ((seller, buyer), (buyer, seller)):
        conns = (await world.client.get("/api/v1/connections", headers=c.h)).json()
        assert [(x["org"]["id"], x["status"], x["source"]) for x in conns] == [
            (other.org_id, "accepted", "match")
        ]
        assert len(await notifications(c.org_id, "match.confirmed")) >= 1
        unseen = (await world.client.get("/api/v1/matches/unseen", headers=c.h)).json()
        assert [u["org"]["id"] for u in unseen] == [other.org_id]
        await world.client.post(f"/api/v1/matches/{unseen[0]['id']}/seen", headers=c.h)
        assert (await world.client.get("/api/v1/matches/unseen", headers=c.h)).json() == []

    mine = (await world.client.get("/api/v1/matches", headers=buyer.h)).json()
    assert mine[0]["type_label"] == "Comercial: você compra"
    rows = (await world.client.get("/api/v1/likes?filter=matched", headers=seller.h)).json()
    assert {r["status"] for r in rows["groups"][0]["items"]} == {"matched"}

    net_seller = (await world.client.get("/api/v1/network", headers=seller.h)).json()
    groups = {g["key"]: g for g in net_seller["groups"]}
    assert buyer.org_id in [i["org"]["id"] for i in groups["clients"]["items"]]
    assert buyer.org_id in [i["org"]["id"] for i in groups["connected"]["items"]]
    net_buyer = (await world.client.get("/api/v1/network", headers=buyer.h)).json()
    groups = {g["key"]: g for g in net_buyer["groups"]}
    assert seller.org_id in [i["org"]["id"] for i in groups["suppliers"]["items"]]


async def test_sell_sell_and_buy_buy_are_mutual_interest_only(world: World) -> None:
    a = await world.active_company()
    b = await world.active_company()
    await like(world, a, b, "sell")
    res = (await like(world, b, a, "sell")).json()["result"]
    assert res["kind"] == "mutual" and res["match"]["kind"] == "mutual_sell"
    assert res["match"]["status"] == "MUTUAL_INTEREST"
    assert (await world.client.get("/api/v1/connections", headers=a.h)).json() == []
    assert (await world.client.get("/api/v1/matches/unseen", headers=a.h)).json() == []
    # buy×buy (other pair) is also only a mutual interest
    c = await world.active_company()
    d = await world.active_company()
    await like(world, c, d, "buy")
    res = (await like(world, d, c, "buy")).json()["result"]
    assert res["kind"] == "mutual" and res["match"]["kind"] == "mutual_buy"
    rows = (await world.client.get("/api/v1/likes?filter=sent", headers=c.h)).json()
    assert [r["status"] for r in rows["groups"][0]["items"]] == ["mutual"]
    # changing the intent updates the single active like (buy now meets their sell: match)
    res = (await like(world, a, b, "buy")).json()["result"]
    assert res["kind"] == "match" and res["match"]["kind"] == "commercial"
    rows = (await world.client.get("/api/v1/likes?filter=sent", headers=a.h)).json()
    assert len([r for r in rows["groups"][0]["items"] if r["org"]["id"] == b.org_id]) == 1
    assert rows["groups"][0]["items"][0]["status"] == "matched"
    # partnership on both sides becomes a real match
    await like(world, c, d, "part")
    res = (await like(world, d, c, "part")).json()["result"]
    assert res["kind"] == "match" and res["match"]["kind"] == "partnership"


async def test_withdrawn_like_does_not_create_match(world: World) -> None:
    a = await world.active_company()
    b = await world.active_company()
    lk = (await like(world, a, b, "buy")).json()["like"]
    r = await world.client.delete(f"/api/v1/likes/{lk['id']}", headers=a.h)
    assert r.status_code == 200 and r.json()["like"]["status"] == "withdrawn"
    res = (await like(world, b, a, "sell")).json()["result"]
    assert res["kind"] == "unilateral" and res["match"] is None
    assert (await world.client.get("/api/v1/matches", headers=b.h)).json() == []
    # someone else cannot withdraw a like that is not theirs
    lk_b = (await like(world, b, a, "sell")).json()["like"]
    assert (
        await world.client.delete(f"/api/v1/likes/{lk_b['id']}", headers=a.h)
    ).status_code == 404


async def test_self_like_refused(world: World) -> None:
    a = await world.active_company()
    r = await like(world, a, a, "buy")
    assert r.status_code == 422 and r.json()["code"] == "self_like"


async def test_block_wins_both_ways(world: World) -> None:
    a = await world.active_company()
    b = await world.active_company()
    assert card_of(await cards(world, a), b) is not None
    await like(world, b, a, "buy")
    r = await world.client.post(
        "/api/v1/discovery/blocks", headers=a.h, json={"target_org_id": b.org_id}
    )
    assert r.status_code == 200
    assert card_of(await cards(world, a), b) is None
    assert card_of(await cards(world, b), a) is None
    assert (await like(world, a, b, "sell")).status_code == 403
    assert (await like(world, b, a, "buy")).status_code == 403
    # the received like is hidden too, and the page does not exist for the blocked company
    rows = (await world.client.get("/api/v1/likes", headers=a.h)).json()["groups"][0]["items"]
    assert b.org_id not in [r["org"]["id"] for r in rows]
    assert (await world.client.get(f"/api/v1/companies/{a.slug}", headers=b.h)).status_code == 404
    page = (await world.client.get(f"/api/v1/companies/{b.slug}", headers=a.h)).json()
    assert page["relationship"]["blocked"] is True
    r = await world.client.post(
        "/api/v1/connections/request", headers=b.h, json={"target_org_id": a.org_id}
    )
    assert r.status_code == 403
    directory = (await world.client.get("/api/v1/directory", headers=b.h)).json()
    assert a.org_id not in [i["id"] for i in directory["items"] + directory["sponsored"]]
    # unblock brings it back
    assert (
        await world.client.delete(f"/api/v1/discovery/blocks/{b.org_id}", headers=a.h)
    ).status_code == 200
    back = card_of(await cards(world, a), b)
    assert back is not None and back["their_like"]["intent"] == "buy"


async def test_department_visibility_of_likes(world: World) -> None:
    a = await world.active_company()
    wants_to_buy = await world.active_company()
    wants_to_sell = await world.active_company()
    compras = await member(world, a, ["compras"])
    comercial = await member(world, a, ["comercial"])
    await like(world, wants_to_buy, a, "buy")
    await like(world, wants_to_sell, a, "sell")

    def ids(page: dict) -> set[str]:
        return {r["org"]["id"] for g in page["groups"] for r in g["items"]}

    seen_compras = ids((await world.client.get("/api/v1/likes", headers=compras)).json())
    assert wants_to_sell.org_id in seen_compras and wants_to_buy.org_id not in seen_compras
    seen_comercial = ids((await world.client.get("/api/v1/likes", headers=comercial)).json())
    assert wants_to_buy.org_id in seen_comercial and wants_to_sell.org_id not in seen_comercial
    owner = ids((await world.client.get("/api/v1/likes", headers=a.h)).json())
    assert {wants_to_buy.org_id, wants_to_sell.org_id} <= owner
    summary = (await world.client.get("/api/v1/likes/summary", headers=compras)).json()
    assert summary["tabs"]["compras"] == 0 and summary["tabs"]["vendas"] == 1
    # the like notifications reach the right departments only
    buy_notes = await notifications(a.org_id, "like.buy_interest")
    sell_notes = await notifications(a.org_id, "like.sell_interest")
    compras_id = (await world.client.get("/api/v1/auth/me", headers=compras)).json()["user"]["id"]
    assert compras_id in {str(n.user_id) for n in sell_notes}
    assert compras_id not in {str(n.user_id) for n in buy_notes}
    # private purchases: Compras reaches them, Comercial does not
    assert (await world.client.get("/api/v1/purchase-needs", headers=compras)).status_code == 200
    assert (await world.client.get("/api/v1/purchase-needs", headers=comercial)).status_code == 403


async def test_private_purchase_needs_never_reach_another_org(world: World) -> None:
    viewer = await world.active_company()
    target = await world.active_company()
    secret = f"Xilofone Secreto {uuid.uuid4().hex[:6]}"
    supplier_name = f"Fornecedor Oculto {uuid.uuid4().hex[:6]}"
    await offer(world, viewer, secret)  # the viewer SELLS what the target buys in private
    await offer(world, target, "Consultoria logística")

    before = card_of(await cards(world, viewer), target)
    assert before is not None
    await need(
        world,
        target,
        secret,
        price_paid_cents=99999,
        current_supplier=supplier_name,
        volume="9.999 un.",
    )
    published = await need(
        world,
        target,
        "Paletes de madeira",
        visibility="published",
        current_supplier=supplier_name,
        publish_flags={"price": False, "supplier": False, "volume": False},
    )
    after = card_of(await cards(world, viewer), target)
    assert after is not None
    # the private need does not move the compatibility nor show up in the reason
    assert (before["compat"], before["compat_reason"]) == (after["compat"], after["compat_reason"])

    # likes, match and network all around: nothing private leaks
    await like(world, viewer, target, "sell", ["Consultoria"])
    await like(world, target, viewer, "buy")
    blob = await everything_seen_by(world, viewer, target)
    assert secret not in blob
    assert supplier_name not in blob and "99999" not in blob and "9.999" not in blob
    page = (await world.client.get(f"/api/v1/companies/{target.slug}", headers=viewer.h)).json()
    assert [n["name"] for n in page["published_needs"]] == [published["name"]]
    assert "current_supplier" not in page["published_needs"][0]
    assert "buy" in page["open_to"]


async def test_sponsored_flag_does_not_change_compat(world: World) -> None:
    viewer = await world.active_company()
    target = await world.active_company()
    await offer(world, target, "Frascos PET 100 ml")
    before = card_of(await cards(world, viewer), target)
    assert before is not None and before["sponsored"] is False
    async with SessionLocal() as s:
        s.add(
            BoostCampaign(
                org_id=uuid.UUID(target.org_id),
                days=1,
                amount_cents=3900,
                status="active",
                starts_at=datetime.now(UTC) - timedelta(hours=1),
                ends_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await s.commit()
    after = card_of(await cards(world, viewer), target)
    assert after is not None and after["sponsored"] is True
    assert (after["compat"], after["compat_reason"]) == (before["compat"], before["compat_reason"])
    async with SessionLocal() as s:
        stat = (
            await s.execute(select(OrgDayStat).where(OrgDayStat.org_id == uuid.UUID(target.org_id)))
        ).scalar_one()
        assert stat.impressions >= 2 and stat.impressions_sponsored >= 1


async def test_cards_exclude_skipped_and_liked(world: World) -> None:
    viewer = await world.active_company()
    skipped = await world.active_company()
    liked = await world.active_company()
    deck = await cards(world, viewer)
    assert card_of(deck, skipped) and card_of(deck, liked)
    r = await world.client.post(
        "/api/v1/discovery/actions",
        headers=viewer.h,
        json={"target_org_id": skipped.org_id, "action": "skip"},
    )
    assert r.status_code == 200
    await like(world, viewer, liked, "net")
    deck = await cards(world, viewer)
    assert card_of(deck, skipped) is None and card_of(deck, liked) is None
    await world.client.post(
        "/api/v1/discovery/actions",
        headers=viewer.h,
        json={"target_org_id": skipped.org_id, "action": "undo_skip"},
    )
    assert card_of(await cards(world, viewer), skipped) is not None
    # save / saved list / company page counts a visit
    await world.client.post(
        "/api/v1/discovery/actions",
        headers=viewer.h,
        json={"target_org_id": skipped.org_id, "action": "save"},
    )
    saved = (await world.client.get("/api/v1/discovery/saved", headers=viewer.h)).json()
    assert [s["id"] for s in saved] == [skipped.org_id]
    page = (await world.client.get(f"/api/v1/companies/{skipped.slug}", headers=viewer.h)).json()
    assert page["relationship"]["saved"] is True
    async with SessionLocal() as s:
        stat = (
            await s.execute(
                select(OrgDayStat).where(OrgDayStat.org_id == uuid.UUID(skipped.org_id))
            )
        ).scalar_one()
        assert stat.profile_visits == 1


async def test_connection_request_accept(world: World) -> None:
    a = await world.active_company()
    b = await world.active_company()
    r = await world.client.post(
        "/api/v1/connections/request",
        headers=a.h,
        json={"target_org_id": b.org_id, "message": "Olá!"},
    )
    assert r.status_code == 200 and r.json()["status"] == "requested"
    cid = r.json()["id"]
    assert len(await notifications(b.org_id, "connection.request")) >= 1
    # the requester cannot accept its own request
    assert (
        await world.client.post(f"/api/v1/connections/{cid}/accept", headers=a.h)
    ).status_code == 400
    net = (await world.client.get("/api/v1/network", headers=b.h)).json()
    assert [p["org"]["id"] for p in net["pending_requests"]] == [a.org_id]
    r = await world.client.post(f"/api/v1/connections/{cid}/accept", headers=b.h)
    assert r.json()["status"] == "accepted"
    assert len(await notifications(a.org_id, "connection.accepted")) >= 1
    r = await world.client.post(f"/api/v1/connections/{cid}/end", headers=a.h)
    assert r.json()["status"] == "ended"


async def test_ai_recommendation_becomes_match_on_reciprocal_like(world: World) -> None:
    from app.modules.intelligence.models import Recommendation

    buyer = await world.active_company()
    supplier = await world.active_company()
    async with SessionLocal() as s:
        s.add(
            Recommendation(
                org_id=uuid.UUID(buyer.org_id),
                kind="supplier",
                target_org_id=uuid.UUID(supplier.org_id),
                title="Energia por assinatura",
                body="Desconto estimado sobre a conta de energia.",
                score=83,
            )
        )
        await s.commit()
    items = (await world.client.get("/api/v1/matches", headers=buyer.h)).json()
    rec = next(i for i in items if i["org"]["id"] == supplier.org_id)
    assert (rec["origin"], rec["status"], rec["type_label"]) == (
        "AI_RECOMMENDATION",
        "SUGGESTED",
        "Comercial: você compra",
    )
    # the recommended company never sees the recommendation
    assert (await world.client.get("/api/v1/matches", headers=supplier.h)).json() == []
    res = (await like(world, buyer, supplier, "buy")).json()["result"]
    assert res["kind"] == "unilateral" and "recomendada pela IA" in res["message"]
    res = (await like(world, supplier, buyer, "sell")).json()["result"]
    assert res["kind"] == "match"
    items = (await world.client.get("/api/v1/matches", headers=buyer.h)).json()
    mine = [i for i in items if i["org"]["id"] == supplier.org_id]
    assert [(i["status"], i["source"]) for i in mine] == [("MATCH_CONFIRMED", "match")]
    # archiving is per company
    await world.client.post(f"/api/v1/matches/{mine[0]['id']}/archive", headers=buyer.h)
    assert (await world.client.get("/api/v1/matches", headers=buyer.h)).json() == []
    archived = (await world.client.get("/api/v1/matches?archived=true", headers=buyer.h)).json()
    assert len(archived) == 1
    assert len((await world.client.get("/api/v1/matches", headers=supplier.h)).json()) == 1

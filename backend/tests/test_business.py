"""Opportunities (funnel, private notes, close confirmation), conversations (access, unread,
proposal notification, unread e-mails) and chat attachments."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.modules.audit.models import AuditLog
from app.modules.mail.models import EmailMessage
from app.modules.matches.models import Match
from app.modules.messaging import service as messaging
from app.modules.notifications.models import Notification
from tests.conftest import World
from tests.helpers_business import add_member, block, make_connection, make_match

PDF = b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def upload_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN001, ANN201
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "s3_endpoint", "")  # local disk backend
    monkeypatch.setattr(get_settings(), "upload_max_mb", 1)
    return tmp_path


async def _opp(world: World, c, target, kind: str = "sell", title: str = "Embalagens T-500"):  # noqa: ANN001, ANN202
    return await world.client.post(
        "/api/v1/opportunities",
        headers=c.h,
        json={"target_org_id": target.org_id, "kind": kind, "title": title, "product": "T-500"},
    )


# ------------------------------------------------------------------ opportunities


async def test_opportunity_only_between_matched_or_connected(world: World) -> None:
    a, b, c, d = [await world.active_company() for _ in range(4)]
    r = await _opp(world, a, b)
    assert r.status_code == 403 and r.json()["code"] == "no_relation"
    # a mutual interest (sell x sell) is not a confirmed match
    await make_match(a, b, kind="mutual_sell", status="MUTUAL_INTEREST")
    assert (await _opp(world, a, b)).json()["code"] == "no_relation"

    await make_connection(a, c)
    r = await _opp(world, a, c, kind="buy")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "buy" and body["origin_label"] == "Evento"
    assert body["number"].startswith("OP-") and body["stage"] == "new"
    assert body["other_org"]["id"] == c.org_id and body["owner"]["name"]
    # the other side sees the same opportunity as a sale
    seen = (await world.client.get("/api/v1/opportunities", headers=c.h)).json()["items"]
    assert [(o["id"], o["kind"]) for o in seen] == [(body["id"], "sell")]
    assert (await world.client.get("/api/v1/opportunities?kind=sell", headers=a.h)).json()[
        "items"
    ] == []
    assert (
        len((await world.client.get("/api/v1/opportunities?kind=buy", headers=a.h)).json()["items"])
        == 1
    )

    # never with a blocked company, even when connected
    await make_connection(a, d)
    await block(d, a)
    r = await _opp(world, a, d)
    assert r.status_code == 403 and r.json()["code"] == "blocked"


async def test_other_org_cannot_read_opportunity(world: World) -> None:
    a, b, c = [await world.active_company() for _ in range(3)]
    await make_match(b, a)
    opp = (await _opp(world, a, b)).json()
    for method, url in (
        ("get", f"/api/v1/opportunities/{opp['id']}"),
        ("patch", f"/api/v1/opportunities/{opp['id']}"),
        ("put", f"/api/v1/opportunities/{opp['id']}/note"),
        ("post", f"/api/v1/opportunities/{opp['id']}/close"),
    ):
        kwargs = {} if method == "get" else {"json": {"body": "x", "won": True, "stage": "contact"}}
        r = await getattr(world.client, method)(url, headers=c.h, **kwargs)
        assert r.status_code == 404, (method, r.text)
    assert (await world.client.get("/api/v1/opportunities", headers=c.h)).json()["items"] == []
    assert (
        await world.client.get("/api/v1/opportunities/nao-existe", headers=a.h)
    ).status_code == 404


async def test_private_notes_are_isolated(world: World) -> None:
    a, b = await world.active_company(), await world.active_company()
    await make_match(b, a)
    opp = (await _opp(world, a, b)).json()
    r = await world.client.put(
        f"/api/v1/opportunities/{opp['id']}/note", headers=a.h, json={"body": "Margem mínima 18%."}
    )
    assert r.status_code == 200
    await world.client.put(
        f"/api/v1/opportunities/{opp['id']}/note",
        headers=b.h,
        json={"body": "Concorrente: 15 dias."},
    )
    mine = (await world.client.get(f"/api/v1/opportunities/{opp['id']}", headers=a.h)).json()
    theirs = (await world.client.get(f"/api/v1/opportunities/{opp['id']}", headers=b.h)).json()
    assert mine["note"] == "Margem mínima 18%."
    assert theirs["note"] == "Concorrente: 15 dias."
    assert "18%" not in str(theirs) and "15 dias" not in str(mine)


async def test_stage_history_and_owner(world: World) -> None:
    a, b = await world.active_company(), await world.active_company()
    await make_match(b, a)
    opp = (await _opp(world, a, b)).json()
    colleague = await add_member(world, a, ["comercial"], name="Rafael Costa")
    me_b = (await world.client.get("/api/v1/auth/me", headers=b.h)).json()["user"]["id"]
    r = await world.client.patch(
        f"/api/v1/opportunities/{opp['id']}", headers=a.h, json={"owner_user_id": me_b}
    )
    assert r.status_code == 400 and r.json()["code"] == "invalid_owner"
    rafael = (await world.client.get("/api/v1/auth/me", headers=colleague)).json()["user"]["id"]
    r = await world.client.patch(
        f"/api/v1/opportunities/{opp['id']}",
        headers=a.h,
        json={
            "stage": "negotiation",
            "next_action": "Enviar amostras até 19/11",
            "value_estimate_cents": 8_600_000,
            "owner_user_id": rafael,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == "negotiation" and body["owner"]["name"] == "Rafael Costa"
    actions = [h["action"] for h in body["history"]]
    assert actions == ["created", "stage", "next_action", "value", "owner"]
    assert body["history"][1]["from"] == "new" and body["history"][1]["to"] == "negotiation"
    # the other company sees the shared history but not who we put in charge
    other = (await world.client.get(f"/api/v1/opportunities/{opp['id']}", headers=b.h)).json()
    assert [h["action"] for h in other["history"]] == ["created", "stage", "next_action", "value"]
    assert other["owner"] is None and other["stage"] == "negotiation"
    filtered = (
        await world.client.get("/api/v1/opportunities?stage=negotiation", headers=b.h)
    ).json()
    assert len(filtered["items"]) == 1


async def test_close_counts_only_when_both_confirm(world: World) -> None:
    a, b = await world.active_company(), await world.active_company()
    await make_match(b, a)
    opp = (await _opp(world, a, b)).json()
    url = f"/api/v1/opportunities/{opp['id']}/close"
    r = (
        await world.client.post(url, headers=a.h, json={"won": True, "value_cents": 1_800_000})
    ).json()
    assert r["stage"] == "won" and r["closed_value_cents"] == 1_800_000
    assert r["close"]["confirmed"] is False and r["close"]["realized_value_cents"] is None
    theirs = (await world.client.get(f"/api/v1/opportunities/{opp['id']}", headers=b.h)).json()
    assert (
        theirs["close"]["confirmed_by_other"] is True
        and theirs["close"]["confirmed_by_me"] is False
    )
    async with SessionLocal() as s:  # the other company was asked to confirm
        n = (
            (
                await s.execute(
                    select(Notification).where(
                        Notification.org_id == uuid.UUID(b.org_id),
                        Notification.kind == "opportunity.close",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert n
    # a different value restarts the confirmation
    r = (
        await world.client.post(url, headers=b.h, json={"won": True, "value_cents": 1_500_000})
    ).json()
    assert r["close"]["confirmed"] is False and r["close"]["confirmed_by_other"] is False
    r = (await world.client.post(url, headers=a.h, json={"won": True})).json()
    assert r["close"]["confirmed"] is True and r["close"]["realized_value_cents"] == 1_500_000
    # reopening drops the confirmations
    r = (
        await world.client.patch(
            f"/api/v1/opportunities/{opp['id']}", headers=a.h, json={"stage": "proposal"}
        )
    ).json()
    assert r["close"]["confirmed"] is False and r["close"]["realized_value_cents"] is None
    r = (await world.client.post(url, headers=b.h, json={"won": False})).json()
    assert r["stage"] == "lost" and r["close"]["realized_value_cents"] is None


async def test_from_match_is_idempotent_and_opens_conversation(world: World) -> None:
    buyer, seller, outsider = [await world.active_company() for _ in range(3)]
    match_id = await make_match(buyer, seller, product="Bandejas para hortifrúti", score=88)
    r = await world.client.post(f"/api/v1/opportunities/from-match/{match_id}", headers=seller.h)
    assert r.status_code == 200, r.text
    first = r.json()
    opp = first["opportunity"]
    assert first["created"] is True and opp["kind"] == "sell" and opp["compat"] == 88
    assert opp["origin_label"] == "Curtida recíproca" and opp["title"] == "Bandejas para hortifrúti"
    again = (
        await world.client.post(f"/api/v1/opportunities/from-match/{match_id}", headers=buyer.h)
    ).json()
    assert again["created"] is False
    assert (
        again["opportunity"]["id"] == opp["id"]
        and again["conversation_id"] == first["conversation_id"]
    )
    assert again["opportunity"]["kind"] == "buy"
    msgs = (
        await world.client.get(
            f"/api/v1/conversations/{first['conversation_id']}/messages", headers=buyer.h
        )
    ).json()
    assert msgs["items"][0]["kind"] == "system" and "Match confirmado" in msgs["items"][0]["body"]
    async with SessionLocal() as s:
        assert (await s.get(Match, uuid.UUID(match_id))).status == "IN_CONVERSATION"
    r = await world.client.post(f"/api/v1/opportunities/from-match/{match_id}", headers=outsider.h)
    assert r.status_code == 404
    unconfirmed = await make_match(buyer, outsider, kind="mutual_buy", status="MUTUAL_INTEREST")
    r = await world.client.post(f"/api/v1/opportunities/from-match/{unconfirmed}", headers=buyer.h)
    assert r.status_code == 403


# ------------------------------------------------------------------ conversations


async def test_conversation_access_third_org_and_blocked(world: World) -> None:
    a, b, c = [await world.active_company() for _ in range(3)]
    r = await world.client.post(
        "/api/v1/conversations", headers=a.h, json={"target_org_id": b.org_id}
    )
    assert r.status_code == 403 and r.json()["code"] == "no_relation"
    await make_connection(a, b)
    r = await world.client.post(
        "/api/v1/conversations", headers=a.h, json={"target_org_id": b.org_id}
    )
    assert r.status_code == 200, r.text
    conv = r.json()
    assert conv["created"] is True and conv["other_org"]["id"] == b.org_id
    # one general conversation per pair; a new opportunity gets its own conversation
    again = (
        await world.client.post(
            "/api/v1/conversations", headers=b.h, json={"target_org_id": a.org_id}
        )
    ).json()
    assert again["id"] == conv["id"] and again["created"] is False
    opp = (await _opp(world, a, b)).json()
    per_opp = (
        await world.client.post(
            "/api/v1/conversations",
            headers=a.h,
            json={"target_org_id": b.org_id, "opportunity_id": opp["id"]},
        )
    ).json()
    assert per_opp["id"] != conv["id"] and per_opp["opportunity"]["number"] == opp["number"]

    cid = conv["id"]
    for method, url, kw in (
        ("get", f"/api/v1/conversations/{cid}", {}),
        ("get", f"/api/v1/conversations/{cid}/messages", {}),
        ("post", f"/api/v1/conversations/{cid}/messages", {"json": {"body": "oi"}}),
        ("post", f"/api/v1/conversations/{cid}/read", {}),
    ):
        r = await getattr(world.client, method)(url, headers=c.h, **kw)
        assert r.status_code == 404, (url, r.text)
    assert (await world.client.get("/api/v1/conversations", headers=c.h)).json()["items"] == []
    # a department outside "messages" never reads
    fin = await add_member(world, a, ["financeiro"])
    assert (await world.client.get(f"/api/v1/conversations/{cid}", headers=fin)).status_code == 403
    # narrowed to Diretoria on our side: Comercial no longer reads, the owner still does
    sales = await add_member(world, a, ["comercial"])
    assert (
        await world.client.get(f"/api/v1/conversations/{cid}", headers=sales)
    ).status_code == 200
    r = await world.client.put(
        f"/api/v1/conversations/{cid}/participants",
        headers=a.h,
        json={"departments": ["diretoria"]},
    )
    assert r.status_code == 200
    assert (
        await world.client.get(f"/api/v1/conversations/{cid}", headers=sales)
    ).status_code == 403
    assert (await world.client.get(f"/api/v1/conversations/{cid}", headers=a.h)).status_code == 200

    await block(b, a)
    r = await world.client.post(
        f"/api/v1/conversations/{cid}/messages", headers=a.h, json={"body": "oi"}
    )
    assert r.status_code == 403 and r.json()["code"] == "blocked"
    assert (
        await world.client.get(f"/api/v1/conversations/{cid}/messages", headers=b.h)
    ).status_code == 403
    assert (await world.client.get("/api/v1/conversations", headers=a.h)).json()["items"] == []
    r = await world.client.post(
        "/api/v1/conversations", headers=a.h, json={"target_org_id": b.org_id}
    )
    assert r.status_code == 403 and r.json()["code"] == "blocked"


async def test_messages_order_unread_and_read(world: World) -> None:
    a, b = await world.active_company(), await world.active_company()
    match_id = await make_match(b, a)
    start = (
        await world.client.post(f"/api/v1/opportunities/from-match/{match_id}", headers=a.h)
    ).json()
    cid = start["conversation_id"]
    url = f"/api/v1/conversations/{cid}/messages"
    r = await world.client.post(
        url, headers=a.h, json={"kind": "decision", "body": "Volume de referência: 40 mil un./mês"}
    )
    assert r.status_code == 200
    assert r.json()["sender"]["department"] == "Diretoria"
    assert (await world.client.post(url, headers=a.h, json={"body": "  "})).json()[
        "code"
    ] == "empty_message"
    for i in range(3):
        r = await world.client.post(url, headers=b.h, json={"body": f"mensagem {i}"})
        assert r.status_code == 200 and r.json()["mine"] is True

    items = (await world.client.get(url, headers=a.h)).json()["items"]
    assert [m["body"] for m in items][1:] == [
        "Volume de referência: 40 mil un./mês",
        "mensagem 0",
        "mensagem 1",
        "mensagem 2",
    ]
    assert items[2]["mine"] is False and items[2]["sender"]["org"]["id"] == b.org_id
    page = (await world.client.get(f"{url}?limit=2", headers=a.h)).json()
    assert page["has_more"] is True
    assert [m["body"] for m in page["items"]] == ["mensagem 1", "mensagem 2"]
    older = (
        await world.client.get(f"{url}?limit=2&before={page['items'][0]['id']}", headers=a.h)
    ).json()
    assert [m["body"] for m in older["items"]][1:] == ["mensagem 0"]

    lst = (await world.client.get("/api/v1/conversations", headers=a.h)).json()
    row = next(c for c in lst["items"] if c["id"] == cid)
    assert row["unread"] == 3 and lst["unread"] >= 3
    assert row["opportunity"]["stage"] == "new" and row["other_org"]["id"] == b.org_id
    assert row["last_message"]["preview"] == "mensagem 2"
    theirs = (await world.client.get("/api/v1/conversations", headers=b.h)).json()["items"][0]
    assert theirs["unread"] == 0  # replying marks the conversation read; own messages never count
    detail = (await world.client.get(f"/api/v1/conversations/{cid}", headers=b.h)).json()
    assert len(detail["decisions"]) == 1 and detail["opportunity"]["number"].startswith("OP-")
    assert {p["slug"] for p in detail["participants"]["mine"]} == {
        "diretoria",
        "comercial",
        "compras",
        "rh",
    }

    assert (
        await world.client.post(f"/api/v1/conversations/{cid}/read", headers=a.h)
    ).status_code == 200
    row = next(
        c
        for c in (await world.client.get("/api/v1/conversations", headers=a.h)).json()["items"]
        if c["id"] == cid
    )
    assert row["unread"] == 0


async def test_realtime_push_reaches_both_orgs(world: World) -> None:
    from app.core import realtime

    a, b = await world.active_company(), await world.active_company()
    await make_connection(a, b)
    conv = (
        await world.client.post(
            "/api/v1/conversations", headers=a.h, json={"target_org_id": b.org_id}
        )
    ).json()
    ids = {}
    for c in (a, b):
        ids[c.org_id] = uuid.UUID(
            (await world.client.get("/api/v1/auth/me", headers=c.h)).json()["user"]["id"]
        )
    queues = {k: realtime.subscribe(v) for k, v in ids.items()}
    try:
        await world.client.post(
            f"/api/v1/conversations/{conv['id']}/messages", headers=a.h, json={"body": "Olá!"}
        )
        got_a = queues[a.org_id].get_nowait()
        got_b = queues[b.org_id].get_nowait()
        assert got_a["type"] == got_b["type"] == "message"
        assert got_a["message"]["mine"] is True and got_b["message"]["mine"] is False
    finally:
        for k, q in queues.items():
            realtime.unsubscribe(ids[k], q)


async def test_proposal_request_notifies_other_org(world: World) -> None:
    a, b = await world.active_company(), await world.active_company()
    match_id = await make_match(b, a)
    cid = (
        await world.client.post(f"/api/v1/opportunities/from-match/{match_id}", headers=b.h)
    ).json()["conversation_id"]
    r = await world.client.post(
        f"/api/v1/conversations/{cid}/messages",
        headers=b.h,
        json={
            "kind": "proposal_request",
            "body": "Cotação para 40 mil un./mês",
            "data": {"quantity": 40000, "evil": "x"},
        },
    )
    assert r.status_code == 200 and r.json()["data"] == {"quantity": 40000}
    async with SessionLocal() as s:
        rows = (
            (
                await s.execute(
                    select(Notification).where(
                        Notification.org_id == uuid.UUID(a.org_id),
                        Notification.kind == "proposal.received",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1 and rows[0].link == f"/app/mensagens/{cid}"
        mine = (
            (
                await s.execute(
                    select(Notification).where(
                        Notification.org_id == uuid.UUID(b.org_id),
                        Notification.kind == "proposal.received",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert mine == []
        mails = (
            (
                await s.execute(
                    select(EmailMessage).where(
                        EmailMessage.to_email == a.email,
                        EmailMessage.template_key == "proposal.received",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(mails) == 1


async def test_unread_mail_once_per_hour(world: World) -> None:
    a, b = await world.active_company(), await world.active_company()
    await make_connection(a, b)
    cid = (
        await world.client.post(
            "/api/v1/conversations", headers=a.h, json={"target_org_id": b.org_id}
        )
    ).json()["id"]
    await world.client.post(
        f"/api/v1/conversations/{cid}/messages", headers=a.h, json={"body": "Tudo bem?"}
    )

    async def mails() -> int:
        async with SessionLocal() as s:
            return len(
                (
                    await s.execute(
                        select(EmailMessage).where(
                            EmailMessage.to_email == b.email,
                            EmailMessage.template_key == "message.new",
                        )
                    )
                )
                .scalars()
                .all()
            )

    async def tick(minutes: int) -> None:
        async with SessionLocal() as s:
            await messaging.tick(s, at=datetime.now(UTC) + timedelta(minutes=minutes))
            await s.commit()

    try:
        await tick(10)  # not 30 minutes yet
        assert await mails() == 0
        await tick(31)
        assert await mails() == 1
        await tick(45)  # same hour
        assert await mails() == 1
        await tick(120)  # nothing new since the last e-mail
        assert await mails() == 1
        # the sender never gets mailed about its own message
        async with SessionLocal() as s:
            sent = (
                (
                    await s.execute(
                        select(EmailMessage).where(
                            EmailMessage.to_email == a.email,
                            EmailMessage.template_key == "message.new",
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert sent == []
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(AuditLog).where(AuditLog.target_id == cid))
            await s.commit()


async def test_read_conversation_is_not_mailed(world: World) -> None:
    a, b = await world.active_company(), await world.active_company()
    await make_connection(a, b)
    cid = (
        await world.client.post(
            "/api/v1/conversations", headers=a.h, json={"target_org_id": b.org_id}
        )
    ).json()["id"]
    await world.client.post(
        f"/api/v1/conversations/{cid}/messages", headers=a.h, json={"body": "Oi"}
    )
    await world.client.post(f"/api/v1/conversations/{cid}/read", headers=b.h)
    async with SessionLocal() as s:
        assert await messaging.tick(s, at=datetime.now(UTC) + timedelta(minutes=40)) == 0
        await s.rollback()


# ------------------------------------------------------------------ uploads


async def test_upload_limits_and_access(world: World, upload_dir) -> None:  # noqa: ANN001
    a, b, c = [await world.active_company() for _ in range(3)]
    await make_connection(a, b)
    await make_connection(a, c)
    up = "/api/v1/uploads"
    r = await world.client.post(
        up, headers=a.h, files={"file": ("virus.exe", b"MZ...", "application/octet-stream")}
    )
    assert r.status_code == 400 and r.json()["code"] == "file_type"
    r = await world.client.post(
        up, headers=a.h, files={"file": ("falso.pdf", b"MZ not a pdf", "application/pdf")}
    )
    assert r.status_code == 400 and r.json()["code"] == "file_type"
    big = b"%PDF" + b"0" * (1024 * 1024 + 10)
    r = await world.client.post(
        up, headers=a.h, files={"file": ("grande.pdf", big, "application/pdf")}
    )
    assert r.status_code == 413 and r.json()["code"] == "file_too_large"
    assert not any(p.is_file() for p in upload_dir.rglob("*"))

    r = await world.client.post(
        up, headers=a.h, files={"file": ("Ficha técnica T-500.pdf", PDF, "application/pdf")}
    )
    assert r.status_code == 200, r.text
    file = r.json()
    assert file["mime"] == "application/pdf" and file["size"] == len(PDF)
    assert (upload_dir / a.slug / "chat" / file["id"]).is_file()
    # uploader's company reads it; others don't until it is sent in a conversation with them
    got = await world.client.get(f"{up}/{file['id']}", headers=a.h)
    assert got.status_code == 200 and got.content == PDF
    assert (await world.client.get(f"{up}/{file['id']}", headers=b.h)).status_code == 404

    conv = (
        await world.client.post(
            "/api/v1/conversations", headers=a.h, json={"target_org_id": b.org_id}
        )
    ).json()
    # b cannot attach a file of a
    r = await world.client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=b.h,
        json={"kind": "attachment", "data": {"upload_id": file["id"]}},
    )
    assert r.status_code == 400 and r.json()["code"] == "upload_not_found"
    r = await world.client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=a.h,
        json={
            "kind": "attachment",
            "body": "Segue a ficha",
            "data": {"upload_id": file["id"], "name": "outro.exe", "size": 1},
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Ficha técnica T-500.pdf" and r.json()["data"][
        "size"
    ] == len(PDF)
    got = await world.client.get(f"{up}/{file['id']}", headers=b.h)
    assert got.status_code == 200 and got.content == PDF
    assert (await world.client.get(f"{up}/{file['id']}", headers=c.h)).status_code == 404
    assert (await world.client.get(f"{up}/../../etc", headers=c.h)).status_code == 404
    await block(a, b)
    assert (await world.client.get(f"{up}/{file['id']}", headers=b.h)).status_code == 404

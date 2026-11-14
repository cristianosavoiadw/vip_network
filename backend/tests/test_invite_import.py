"""Team-panel invites without CNPJ and the Excel import (owner request 2026-11-14)."""

from __future__ import annotations

import io

from openpyxl import Workbook, load_workbook
from sqlalchemy import select

from app.db.session import SessionLocal
from app.modules.auth import service as auth
from app.modules.invites.models import Invite
from tests.conftest import PASSWORD, World


async def _admin(world: World) -> dict[str, str]:
    email = world.email()
    async with SessionLocal() as s:
        await auth.create_user(s, email=email, password=PASSWORD, kind="admin", admin_role="owner")
        await s.commit()
    r = await world.client.post(
        "/api/v1/auth/admin/login", json={"email": email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sheet(rows: list[list[str]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Convites"
    ws.append(["Nome", "Sobrenome", "E-mail", "Empresa", "Mensagem (opcional)"])
    for r in rows:
        ws.append(r)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


async def test_staff_invite_needs_names_not_cnpj(world: World) -> None:
    h = await _admin(world)
    email = world.email()
    r = await world.client.post(
        "/api/v1/admin/access/invites",
        headers=h,
        json={
            "first_name": "Paula",
            "last_name": "Reis",
            "email": email,
            "company_name": "Horizonte",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["first_name"] == "Paula" and "cnpj" not in r.json()
    again = await world.client.post(
        "/api/v1/admin/access/invites",
        headers=h,
        json={
            "first_name": "Paula",
            "last_name": "Reis",
            "email": email,
            "company_name": "Horizonte",
        },
    )
    assert again.json()["code"] == "already_invited"


async def test_template_downloads_with_layout(world: World) -> None:
    h = await _admin(world)
    r = await world.client.get("/api/v1/admin/access/invites/template", headers=h)
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.content))["Convites"]
    assert [c.value for c in ws[1]][:4] == ["Nome", "Sobrenome", "E-mail", "Empresa"]


async def test_import_preview_then_send_only_valid_rows(world: World) -> None:
    h = await _admin(world)
    good1, good2, taken = world.email(), world.email(), world.email()
    async with SessionLocal() as s:  # an e-mail that already has an account
        await auth.create_user(s, email=taken, password=PASSWORD)
        await s.commit()
    data = _sheet(
        [
            ["Ana", "Souza", good1, "Empresa Um", "Bem-vinda"],
            ["Bruno", "Lima", good2, "Empresa Dois", ""],
            ["Carla", "", world.email(), "Empresa Três", ""],
            ["Davi", "Rocha", "nao-e-email", "Empresa Quatro", ""],
            ["Eva", "Melo", good1, "Repetida", ""],
            ["Fábio", "Dias", taken, "Já tem conta", ""],
        ]
    )
    files = {
        "file": (
            "convites.xlsx",
            data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    preview = (
        await world.client.post("/api/v1/admin/access/invites/import", headers=h, files=files)
    ).json()
    assert preview["total"] == 6 and preview["ok"] == 2 and preview["sent"] == 0
    errors = {r["row"]: r["error"] for r in preview["rows"] if r["status"] == "error"}
    assert errors[4] == "Falta o sobrenome."
    assert errors[5] == "E-mail inválido."
    assert errors[6] == "E-mail repetido na planilha."
    assert "já tem conta" in errors[7]
    async with SessionLocal() as s:
        assert not (await s.execute(select(Invite).where(Invite.email == good1))).first()

    sent = (
        await world.client.post(
            "/api/v1/admin/access/invites/import?send=true", headers=h, files=files
        )
    ).json()
    assert sent["sent"] == 2
    async with SessionLocal() as s:
        rows = list(
            (await s.execute(select(Invite).where(Invite.email.in_([good1, good2])))).scalars()
        )
        assert {r.first_name for r in rows} == {"Ana", "Bruno"} and all(r.cnpj == "" for r in rows)


async def test_import_rejects_wrong_layout(world: World) -> None:
    h = await _admin(world)
    wb = Workbook()
    wb.active.append(["Email", "Nome"])
    out = io.BytesIO()
    wb.save(out)
    r = await world.client.post(
        "/api/v1/admin/access/invites/import",
        headers=h,
        files={"file": ("x.xlsx", out.getvalue(), "application/octet-stream")},
    )
    assert r.json()["code"] == "bad_layout"


async def test_staff_invite_uses_its_own_email_template(world: World) -> None:
    from app.modules.mail.models import EmailMessage

    h = await _admin(world)
    email = world.email()
    r = await world.client.post(
        "/api/v1/admin/access/invites",
        headers=h,
        json={
            "first_name": "Rita",
            "last_name": "Alves",
            "email": email,
            "company_name": "Alves Ltda",
        },
    )
    assert r.status_code == 200, r.text
    async with SessionLocal() as s:
        msg = (
            await s.execute(select(EmailMessage).where(EmailMessage.to_email == email))
        ).scalar_one()
    assert msg.template_key == "invite.staff"
    assert msg.subject == "Rita, você foi convidado para a VIP Network"

"""Bulk invites for the team panel (owner request 2026-11-14): download a ready Excel layout,
fill it, upload it, review the checked rows and send.

Columns of the "Convites" sheet: Nome, Sobrenome, E-mail, Empresa, Mensagem (optional).
The e-mail identifies the invite; no CNPJ is asked.
"""

from __future__ import annotations

import io
from typing import Any

from email_validator import EmailNotValidError, validate_email
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.invites import service
from app.modules.invites.models import Invite

COLUMNS = (
    ("first_name", "Nome", 22),
    ("last_name", "Sobrenome", 24),
    ("email", "E-mail", 36),
    ("company_name", "Empresa", 34),
    ("message", "Mensagem (opcional)", 50),
)
SHEET = "Convites"
MAX_ROWS = 500
NAVY = "0B1630"
GOLD = "C9A14A"


def template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    for idx, (_key, label, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=idx, value=label)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"
    email_rule = DataValidation(
        type="custom",
        formula1='=ISNUMBER(SEARCH("@",C2))',
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="E-mail",
        error="Digite um e-mail válido.",
    )
    ws.add_data_validation(email_rule)
    email_rule.add(f"C2:C{MAX_ROWS + 1}")

    info = wb.create_sheet("Como preencher")
    info.column_dimensions["A"].width = 110
    lines = [
        ("Convites VIP Network", True),
        ("", False),
        ("1. Preencha uma linha por pessoa na aba “Convites”, a partir da linha 2.", False),
        ("2. Nome, Sobrenome, E-mail e Empresa são obrigatórios. A Mensagem é opcional.", False),
        (
            "3. O convite vale para o e-mail informado: a pessoa precisa se cadastrar com ele.",
            False,
        ),
        (
            "4. E-mails repetidos, que já têm conta ou que já têm convite pendente são apontados",
            False,
        ),
        ("   na prévia e não são enviados.", False),
        (
            f"5. Até {MAX_ROWS} convites por planilha. Não mude a ordem nem o nome das colunas.",
            False,
        ),
        ("", False),
        ("Exemplo (não copie esta linha para a aba Convites):", True),
        (
            "Marina | Andrade | marina@andradeembalagens.com.br | Andrade Embalagens | Quero você na rede",
            False,
        ),
    ]
    for i, (text, bold) in enumerate(lines, start=1):
        c = info.cell(row=i, column=1, value=text)
        c.font = Font(bold=bold, size=13 if i == 1 else 11, color=NAVY if bold else "2D3954")
    info.cell(row=1, column=1).font = Font(bold=True, size=14, color=GOLD)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def parse(data: bytes) -> list[dict[str, Any]]:
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - any broken file
        raise AppError(
            "Não foi possível ler a planilha. Use o modelo em Excel (.xlsx).", code="bad_file"
        ) from exc
    ws = wb[SHEET] if SHEET in wb.sheetnames else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise AppError("A planilha está vazia.", code="empty_file")
    header = [_norm(c).lower() for c in rows[0]]
    expected = [label.lower() for _k, label, _w in COLUMNS[:4]]
    if header[:4] != expected:
        raise AppError(
            "As colunas não batem com o modelo. Baixe o modelo de novo e preencha sem mudar o "
            "cabeçalho.",
            code="bad_layout",
        )
    out: list[dict[str, Any]] = []
    for number, raw in enumerate(rows[1:], start=2):
        values = [_norm(c) for c in (list(raw) + [None] * len(COLUMNS))[: len(COLUMNS)]]
        if not any(values):
            continue
        out.append(
            {"row": number, **{k: v for (k, _l, _w), v in zip(COLUMNS, values, strict=True)}}
        )
    if len(out) > MAX_ROWS:
        raise AppError(f"Máximo de {MAX_ROWS} convites por planilha.", code="too_many_rows")
    if not out:
        raise AppError("Nenhuma linha preenchida na aba Convites.", code="empty_file")
    return out


async def check(session: AsyncSession, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark each row ok or with the reason it would be refused."""
    emails: list[str] = []
    for r in rows:
        try:
            r["email"] = validate_email(r["email"], check_deliverability=False).normalized.lower()
            emails.append(r["email"])
        except EmailNotValidError:
            pass
    existing_users = set(
        (await session.execute(select(User.email).where(User.email.in_(emails)))).scalars()
    )
    pending = set(
        (
            await session.execute(
                select(Invite.email).where(Invite.email.in_(emails), Invite.status == "pending")
            )
        ).scalars()
    )
    seen: set[str] = set()
    for r in rows:
        error = ""
        if len(r["first_name"]) < 2:
            error = "Falta o nome."
        elif len(r["last_name"]) < 2:
            error = "Falta o sobrenome."
        elif "@" not in r["email"] or r["email"] not in emails:
            error = "E-mail inválido."
        elif len(r["company_name"]) < 2:
            error = "Falta o nome da empresa."
        elif r["email"] in seen:
            error = "E-mail repetido na planilha."
        elif r["email"] in existing_users:
            error = "Este e-mail já tem conta na VIP Network."
        elif r["email"] in pending:
            error = "Já existe convite aguardando cadastro para este e-mail."
        if r["email"]:
            seen.add(r["email"])
        r["status"] = "error" if error else "ok"
        r["error"] = error
    return rows


async def run(session: AsyncSession, data: bytes, *, user: User, send: bool) -> dict[str, Any]:
    rows = await check(session, parse(data))
    sent = 0
    if send:
        for r in rows:
            if r["status"] != "ok":
                continue
            try:
                async with session.begin_nested():
                    await service.create(
                        session,
                        org=None,
                        user=user,
                        first_name=r["first_name"],
                        last_name=r["last_name"],
                        company_name=r["company_name"],
                        email=r["email"],
                        message=r["message"],
                        by_staff=True,
                    )
                r["status"] = "sent"
                sent += 1
            except AppError as exc:
                r["status"] = "error"
                r["error"] = exc.message
    return {
        "rows": rows,
        "total": len(rows),
        "ok": sum(1 for r in rows if r["status"] in ("ok", "sent")),
        "errors": sum(1 for r in rows if r["status"] == "error"),
        "sent": sent,
    }

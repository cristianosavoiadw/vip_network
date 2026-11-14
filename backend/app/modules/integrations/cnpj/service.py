"""Lookup a CNPJ: validate, reuse a recent answer, then ask providers in the configured order.

Ported from BR Licitar (plataformas/gov_tech, same chain): our own Receita base read directly
(``marketdb``), then the AIWare API (``aiware``), then the public ``cnpja`` fallback. Every
answer is kept in ``cnpj_records`` for 30 days.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.modules.integrations.cnpj.models import CnpjRecord
from app.modules.integrations.cnpj.providers import (
    CnpjProvider,
    ProviderNotFound,
    ProviderUnavailable,
    registry,
)
from app.modules.integrations.cnpj.schemas import CompanyInfo
from app.modules.integrations.cnpj.validation import format_cnpj, is_valid_cnpj, only_digits

log = logging.getLogger("vip.cnpj")


class CnpjInvalid(AppError):
    status_code = 422
    code = "cnpj_invalid"


class CnpjUnavailable(AppError):
    status_code = 503
    code = "cnpj_unavailable"


# the public fallback: a few calls a minute, never for bulk work
PUBLIC_PROVIDERS = {"cnpja"}
RECORD_DAYS = 30  # a CNPJ looked up is not asked again for this long (the base reloads monthly)


def configured_providers() -> list[CnpjProvider]:
    names = [n.strip() for n in get_settings().cnpj_providers.split(",") if n.strip()]
    reg = registry()
    return [reg[n] for n in names if n in reg]


def own_providers() -> list[CnpjProvider]:
    """Our own CNPJ base (direct read, then its API): no usage limit."""
    return [p for p in configured_providers() if p.name not in PUBLIC_PROVIDERS]


def public_providers() -> list[CnpjProvider]:
    return [p for p in configured_providers() if p.name in PUBLIC_PROVIDERS]


def usable(info: CompanyInfo, digits: str) -> CompanyInfo | None:
    """A provider answer we can build a company from: it names the company and is about the
    CNPJ asked. A blank answer once created a supplier with no name and no CNPJ (2026-10-29)."""
    if info.cnpj and info.cnpj != digits:
        return None
    if not (info.legal_name or info.trade_name).strip():
        return None
    if not info.cnpj:
        info = info.model_copy(update={"cnpj": digits, "cnpj_formatted": format_cnpj(digits)})
    return info


async def recorded(session: AsyncSession, digits: str) -> CnpjRecord | None:
    """The kept lookup of a CNPJ while it is fresh (any status)."""
    r = await session.get(CnpjRecord, digits)
    if r is None or r.fetched_at < datetime.now(UTC) - timedelta(days=RECORD_DAYS):
        return None
    return r


async def keep(
    session: AsyncSession, digits: str, status: str, info: CompanyInfo | None = None
) -> None:
    """Store (or refresh) the outcome of a lookup."""
    values = {
        "cnpj": digits,
        "status": status,
        "data": info.model_dump(mode="json") if info else {},
        "source": info.source if info else "",
        "fetched_at": datetime.now(UTC),
    }
    stmt = insert(CnpjRecord).values(**values, attempts=1)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[CnpjRecord.cnpj],
            set_={
                **{k: v for k, v in values.items() if k != "cnpj"},
                "attempts": CnpjRecord.attempts + 1,
            },
        )
    )


async def lookup(
    cnpj: str,
    *,
    providers: list[CnpjProvider] | None = None,
    session: AsyncSession | None = None,
) -> CompanyInfo:
    """With a session, a company found in the last 30 days comes from ``cnpj_records`` and a
    new answer is kept there."""
    digits = only_digits(cnpj)
    if not is_valid_cnpj(digits):
        raise CnpjInvalid("CNPJ inválido. Confira os 14 dígitos.")

    if session is not None:
        rec = await recorded(session, digits)
        if rec is not None and rec.status == "found" and rec.data:
            kept = usable(CompanyInfo.model_validate(rec.data), digits)
            if kept is not None:
                return kept
    chain = providers if providers is not None else configured_providers()
    if not chain:
        raise CnpjUnavailable("Nenhum provedor de CNPJ configurado")

    not_found = incomplete = False
    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
        for provider in chain:
            try:
                info = await provider.lookup(digits, client)
            except ProviderNotFound:
                not_found = True
                log.info("cnpj not found", extra={"extra": {"provider": provider.name}})
                continue
            except ProviderUnavailable as exc:
                log.warning(
                    "cnpj provider unavailable",
                    extra={"extra": {"provider": provider.name, "error": str(exc)}},
                )
                continue
            good = usable(info, digits)
            if good is None:
                incomplete = True
                log.warning("cnpj answer incomplete", extra={"extra": {"provider": provider.name}})
                continue
            info = good
            if session is not None:
                await keep(session, digits, "found", info)
            return info

    if incomplete:
        raise NotFound(
            "Não conseguimos confirmar o nome e os dados desta empresa. "
            "Confira o CNPJ e tente de novo; se o número estiver certo, fale com o suporte.",
            code="cnpj_incomplete",
        )
    if not_found:
        raise NotFound(
            "CNPJ não encontrado entre as empresas ativas. "
            "Confira o número ou a situação cadastral.",
            code="cnpj_not_found",
        )
    raise CnpjUnavailable("Consulta de CNPJ indisponível no momento. Tente de novo em instantes.")

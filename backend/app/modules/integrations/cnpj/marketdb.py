"""Direct read-only access to the Receita base (AIWare ``aiware_market`` Postgres).

The table is ``sdr_marketcompany`` (Django model ``sdr.MarketCompany`` in the AIWare
repo): one row per ACTIVE establishment, ~28M rows in production, reloaded monthly.
VIP Network reaches it with its own credential, ``AIDEED_MARKET_DATABASE_URL``
(``postgresql://user:pass@host:5432/aiware_market``), which should be a role with
SELECT on that table only. Nothing is ever written here.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg
import httpx

from app.core.config import get_settings
from app.modules.integrations.cnpj.providers import (
    AIWareProvider,
    ProviderNotFound,
    ProviderUnavailable,
)
from app.modules.integrations.cnpj.schemas import CompanyInfo

log = logging.getLogger("vip.cnpj")

_COLUMNS = (
    "cnpj, razao_social, nome_fantasia, cnae_principal, cnae_descricao, natureza_descricao, "
    "porte, capital_social, uf, municipio, logradouro, numero, complemento, bairro, cep, "
    "email, telefone, situacao_cadastral, data_inicio, socio_admin, socios_json"
)
_SQL = f"SELECT {_COLUMNS} FROM sdr_marketcompany WHERE cnpj = $1 LIMIT 1"  # noqa: S608

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is None:
            dsn = get_settings().market_database_url
            _pool = await asyncpg.create_pool(
                dsn,
                min_size=0,
                max_size=4,
                command_timeout=10,
                server_settings={
                    "application_name": "vip-cnpj",
                    "default_transaction_read_only": "on",
                },
            )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _row_to_aiware_shape(row: asyncpg.Record) -> dict[str, Any]:
    """Same keys as AIWare's /sdr/market/company payload, so one mapper serves both."""
    socios = row["socios_json"]
    if isinstance(socios, str):
        import json

        try:
            socios = json.loads(socios)
        except ValueError:
            socios = []
    return {
        "cnpj": row["cnpj"],
        "razao_social": row["razao_social"],
        "nome_fantasia": row["nome_fantasia"],
        "cnae": row["cnae_principal"],
        "cnae_descricao": row["cnae_descricao"],
        "natureza": row["natureza_descricao"],
        "porte": row["porte"],
        "capital_social": float(row["capital_social"] or 0),
        "uf": row["uf"],
        "municipio": row["municipio"],
        "logradouro": row["logradouro"],
        "numero": row["numero"],
        "complemento": row["complemento"],
        "bairro": row["bairro"],
        "cep": row["cep"],
        "email": row["email"],
        "telefone": row["telefone"],
        "situacao_cadastral": row["situacao_cadastral"],
        "data_inicio": row["data_inicio"].isoformat() if row["data_inicio"] else None,
        "socio_admin": row["socio_admin"],
        "socios": socios or [],
    }


class MarketDbProvider:
    name = "marketdb"

    async def lookup(self, cnpj: str, client: httpx.AsyncClient) -> CompanyInfo:
        if not get_settings().market_database_url:
            raise ProviderUnavailable("marketdb not configured")
        try:
            pool = await _get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(_SQL, cnpj)
        except (TimeoutError, asyncpg.PostgresError, OSError) as exc:
            raise ProviderUnavailable(f"marketdb query failed: {exc!r}") from exc
        if row is None:
            raise ProviderNotFound("not in sdr_marketcompany")
        info = AIWareProvider._map(_row_to_aiware_shape(row))
        return info.model_copy(update={"source": "marketdb"})

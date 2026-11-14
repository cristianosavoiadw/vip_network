"""CNPJ providers.

``aiware``: our own copy of the Receita Federal open data (table ``sdr_marketcompany``
in the AIWare ``aiware_market`` database), exposed by AIWare at
``GET /api/v1/sdr/market/company?cnpj=`` with ``Authorization: Token <key>``.
Only active establishments exist there, so "not found" also covers closed companies.

``cnpja``: the public ``open.cnpja.com`` API, no key, used as a fallback when AIWare
is not configured or is down. Same rules AIWare's ``core/cnpj.py`` applies.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any, Protocol

import httpx

from app.core.config import get_settings
from app.modules.integrations.cnpj.schemas import SIZE_LABELS, Address, CompanyInfo, Partner
from app.modules.integrations.cnpj.validation import format_cnpj, only_digits, partner_role

log = logging.getLogger("vip.cnpj")


class ProviderNotFound(Exception):
    """The provider answered and does not know this CNPJ (or it is inactive)."""


class ProviderUnavailable(Exception):
    """Network/HTTP/config failure: try the next provider."""


class CnpjProvider(Protocol):
    name: str

    async def lookup(self, cnpj: str, client: httpx.AsyncClient) -> CompanyInfo: ...


def _s(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# ------------------------------------------------------------------ AIWare


class AIWareProvider:
    name = "aiware"

    async def lookup(self, cnpj: str, client: httpx.AsyncClient) -> CompanyInfo:
        s = get_settings()
        if not s.aiware_api_url or not s.aiware_api_token:
            raise ProviderUnavailable("aiware not configured")
        url = f"{s.aiware_api_url.rstrip('/')}/api/v1/sdr/market/company"
        try:
            r = await client.get(
                url,
                params={"cnpj": cnpj},
                headers={
                    "Authorization": f"Token {s.aiware_api_token}",
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"aiware request failed: {exc!r}") from exc
        if r.status_code in (401, 403):
            raise ProviderUnavailable(f"aiware auth rejected ({r.status_code})")
        if r.status_code >= 500:
            raise ProviderUnavailable(f"aiware http {r.status_code}")
        try:
            body = r.json()
        except ValueError as exc:
            raise ProviderUnavailable("aiware returned non-JSON") from exc
        if not isinstance(body, dict) or not body.get("success"):
            raise ProviderNotFound(_s(body.get("error")) if isinstance(body, dict) else "")
        return self._map(body["company"])

    @staticmethod
    def _map(c: dict[str, Any]) -> CompanyInfo:
        size = _s(c.get("porte")) or "00"
        partners = [
            Partner(name=_s(p.get("nome")), role=partner_role(_s(p.get("qualificacao"))))
            for p in (c.get("socios") or [])
            if isinstance(p, dict) and _s(p.get("nome"))
        ]
        return CompanyInfo(
            cnpj=only_digits(c.get("cnpj")),
            cnpj_formatted=format_cnpj(only_digits(c.get("cnpj"))),
            legal_name=_s(c.get("razao_social")),
            trade_name=_s(c.get("nome_fantasia")),
            cnae_code=_s(c.get("cnae")),
            cnae_description=_s(c.get("cnae_descricao")),
            legal_nature=_s(c.get("natureza")),
            size_code=size,
            size_label=SIZE_LABELS.get(size, size),
            share_capital=float(c["capital_social"])
            if c.get("capital_social") is not None
            else None,
            is_active=_s(c.get("situacao_cadastral")) in ("", "02"),
            status_text="Ativa"
            if _s(c.get("situacao_cadastral")) in ("", "02")
            else _s(c.get("situacao_cadastral")),
            founded=_date(c.get("data_inicio")),
            address=Address(
                street=_s(c.get("logradouro")),
                number=_s(c.get("numero")),
                complement=_s(c.get("complemento")),
                district=_s(c.get("bairro")),
                city=_s(c.get("municipio")),
                state=_s(c.get("uf")).upper(),
                zip=only_digits(c.get("cep")),
            ),
            email=_s(c.get("email")).lower(),
            phone=only_digits(c.get("telefone")),
            admin_partner=_s(c.get("socio_admin")),
            partners=partners,
            source="aiware",
            fetched_at=datetime.now(UTC),
        )


# ------------------------------------------------------------------- CNPJá


class CnpjaProvider:
    name = "cnpja"
    url = "https://open.cnpja.com/office/{cnpj}"

    async def lookup(self, cnpj: str, client: httpx.AsyncClient) -> CompanyInfo:
        try:
            r = await client.get(self.url.format(cnpj=cnpj), headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"cnpja request failed: {exc!r}") from exc
        if r.status_code == 404:
            raise ProviderNotFound("not found")
        if r.status_code == 429 or r.status_code >= 500:
            raise ProviderUnavailable(f"cnpja http {r.status_code}")
        try:
            body = r.json()
        except ValueError as exc:
            raise ProviderUnavailable("cnpja returned non-JSON") from exc
        if not isinstance(body, dict):
            raise ProviderUnavailable("cnpja unexpected payload")
        info = self._map(body)
        if not info.is_active:
            raise ProviderNotFound("inactive")
        return info

    @staticmethod
    def _map(p: dict[str, Any]) -> CompanyInfo:
        company = p.get("company") if isinstance(p.get("company"), dict) else {}
        address = p.get("address") if isinstance(p.get("address"), dict) else {}
        status = p.get("status") if isinstance(p.get("status"), dict) else {}
        status_text = _s(status.get("text"))
        inactive_tokens = ("baixad", "inapt", "suspens", "nula")
        is_active = not any(t in status_text.lower() for t in inactive_tokens)

        size = company.get("size") if isinstance(company.get("size"), dict) else {}
        size_acronym = _s(size.get("acronym")).upper()
        size_code = {"ME": "01", "EPP": "03", "DEMAIS": "05"}.get(size_acronym, "00")

        nature = company.get("nature") if isinstance(company.get("nature"), dict) else {}
        main = p.get("mainActivity") if isinstance(p.get("mainActivity"), dict) else {}

        emails = p.get("emails") if isinstance(p.get("emails"), list) else []
        phones = p.get("phones") if isinstance(p.get("phones"), list) else []
        phone = ""
        if phones and isinstance(phones[0], dict):
            phone = only_digits(f"{_s(phones[0].get('area'))}{_s(phones[0].get('number'))}")

        partners: list[Partner] = []
        admin_partner = ""
        for m in company.get("members") or []:
            if not isinstance(m, dict):
                continue
            person = m.get("person") if isinstance(m.get("person"), dict) else {}
            role = m.get("role") if isinstance(m.get("role"), dict) else {}
            name = _s(person.get("name"))
            if not name:
                continue
            role_text = _s(role.get("text"))
            partners.append(Partner(name=name, role=role_text))
            if "administrador" in role_text.lower() and not admin_partner:
                admin_partner = name

        digits = only_digits(_s(p.get("taxId")))
        return CompanyInfo(
            cnpj=digits,
            cnpj_formatted=format_cnpj(digits),
            legal_name=_s(company.get("name")),
            trade_name=_s(p.get("alias")),
            cnae_code=only_digits(_s(main.get("id"))),
            cnae_description=_s(main.get("text")),
            legal_nature=_s(nature.get("text")),
            size_code=size_code,
            size_label=SIZE_LABELS.get(size_code, _s(size.get("text"))),
            share_capital=float(company["equity"]) if company.get("equity") is not None else None,
            is_active=is_active,
            status_text=status_text or ("Ativa" if is_active else ""),
            founded=_date(p.get("founded")),
            address=Address(
                street=_s(address.get("street")),
                number=_s(address.get("number")),
                complement=_s(address.get("details")),
                district=_s(address.get("district")),
                city=_s(address.get("city")),
                state=_s(address.get("state")).upper(),
                zip=only_digits(_s(address.get("zip"))),
            ),
            email=_s(emails[0].get("address")).lower()
            if emails and isinstance(emails[0], dict)
            else "",
            phone=phone,
            admin_partner=admin_partner,
            partners=partners,
            source="cnpja",
            fetched_at=datetime.now(UTC),
        )


def _registry() -> dict[str, CnpjProvider]:
    from app.modules.integrations.cnpj.marketdb import MarketDbProvider

    return {
        "marketdb": MarketDbProvider(),
        "aiware": AIWareProvider(),
        "cnpja": CnpjaProvider(),
    }


PROVIDERS: dict[str, CnpjProvider] = {}


def registry() -> dict[str, CnpjProvider]:
    if not PROVIDERS:
        PROVIDERS.update(_registry())
    return PROVIDERS

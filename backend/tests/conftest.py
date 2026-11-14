"""Shared test helpers. Tests run against the local Postgres (docker compose up -d db) with
Stripe simulated and e-mail in log-only mode. Every company and user created here is removed at
the end of the test (``world`` fixture)."""

from __future__ import annotations

import random
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_

from app.db.session import SessionLocal
from app.main import app
from app.modules.auth.models import User
from app.modules.billing.models import TrialClaim
from app.modules.integrations.cnpj import service as cnpj_service
from app.modules.integrations.cnpj.schemas import Address, CompanyInfo
from app.modules.integrations.cnpj.validation import format_cnpj
from app.modules.invites.models import Invite
from app.modules.mail.models import EmailMessage
from app.modules.organizations.models import Organization
from app.modules.settings import service as settings_service
from app.modules.settings.models import PlatformSetting

PASSWORD = "senha-forte-123"


def make_cnpj() -> str:
    base = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    for weights in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        r = sum(d * w for d, w in zip(base, weights, strict=False)) % 11
        base.append(0 if r < 2 else 11 - r)
    return "".join(map(str, base))


def fake_info(cnpj: str, name: str = "Empresa Teste") -> CompanyInfo:
    return CompanyInfo(
        cnpj=cnpj,
        cnpj_formatted=format_cnpj(cnpj),
        legal_name=f"{name.upper()} LTDA",
        trade_name=name,
        cnae_code="22.22-6-00",
        cnae_description="Fabricação de embalagens de material plástico",
        size_label="Empresa de Pequeno Porte (EPP)",
        founded=date(2009, 3, 14),
        address=Address(
            street="Av. Paulista",
            number="1000",
            district="Bela Vista",
            city="São Paulo",
            state="SP",
            zip="01310100",
        ),
        source="fake",
        fetched_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def no_network_cnpj(monkeypatch: pytest.MonkeyPatch) -> None:
    async def lookup(cnpj: str, **_: Any) -> CompanyInfo:
        digits = "".join(c for c in cnpj if c.isdigit())
        return fake_info(digits, f"Empresa {digits[:4]}")

    monkeypatch.setattr(cnpj_service, "lookup", lookup)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@dataclass
class Company:
    cnpj: str
    email: str
    token: str
    org_id: str
    slug: str

    @property
    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass
class World:
    client: AsyncClient
    cnpjs: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    settings_backup: dict[str, Any] | None = None

    def email(self) -> str:
        e = f"t-{secrets.token_hex(5)}@teste.vip"
        self.emails.append(e)
        return e

    def cnpj(self) -> str:
        c = make_cnpj()
        self.cnpjs.append(c)
        return c

    async def set_access(self, **values: Any) -> None:
        async with SessionLocal() as s:
            if self.settings_backup is None:
                self.settings_backup = await settings_service.get(s, "access")
            await settings_service.put(s, "access", values, user_id=None)
            await s.commit()

    async def register(
        self, *, invite_code: str | None = None, cnpj: str | None = None, email: str | None = None
    ) -> Company:
        cnpj = cnpj or self.cnpj()
        if cnpj not in self.cnpjs:
            self.cnpjs.append(cnpj)
        email = email or self.email()
        r = await self.client.post(
            "/api/v1/auth/register",
            json={
                "cnpj": cnpj,
                "full_name": "Marina Andrade",
                "job_title": "CEO",
                "email": email,
                "phone": "11999990000",
                "password": PASSWORD,
                "cnpj_relation": "socio",
                "invite_code": invite_code,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        return Company(cnpj, email, body["access_token"], body["org"]["id"], body["org"]["slug"])

    async def active_company(
        self, *, plan: str = "monthly", invite_code: str | None = None
    ) -> Company:
        c = await self.register(invite_code=invite_code)
        r = await self.client.post("/api/v1/billing/subscribe", json={"plan": plan}, headers=c.h)
        assert r.status_code == 200, r.text
        r = await self.client.post("/api/v1/organizations/me/onboarding/complete", headers=c.h)
        assert r.status_code == 200, r.text
        return c


@pytest.fixture
async def world(client: AsyncClient) -> AsyncIterator[World]:
    w = World(client)
    yield w
    async with SessionLocal() as s:
        if w.settings_backup is not None:
            row = await s.get(PlatformSetting, "access")
            if row is not None:
                row.value = w.settings_backup
        await s.execute(delete(Invite).where(Invite.email.in_(w.emails)))
        await s.execute(delete(TrialClaim).where(TrialClaim.cnpj.in_(w.cnpjs)))
        await s.execute(delete(EmailMessage).where(EmailMessage.to_email.in_(w.emails)))
        await s.execute(delete(User).where(or_(User.email.in_(w.emails))))
        await s.execute(delete(Organization).where(Organization.cnpj.in_(w.cnpjs)))
        await s.commit()

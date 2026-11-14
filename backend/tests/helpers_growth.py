"""Helpers for tests/test_growth.py: team admin, colleagues with departments, catalog rows."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.modules.auth import service as auth
from app.modules.catalog.models import Offer, PurchaseNeed
from tests.conftest import PASSWORD, Company, World


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def admin_headers(world: World) -> dict[str, str]:
    email = world.email()
    async with SessionLocal() as s:
        user = await auth.create_user(
            s, email=email, password=PASSWORD, kind="admin", is_superuser=True, admin_role="owner"
        )
        await s.commit()
        token, _ = create_access_token(user.id, "admin")
    return bearer(token)


async def member_headers(world: World, company: Company, departments: list[str]) -> dict[str, str]:
    email = world.email()
    async with SessionLocal() as s:
        user = await auth.create_user(
            s,
            email=email,
            password=PASSWORD,
            org_id=uuid.UUID(company.org_id),
            departments=departments,
            full_name="Colega Teste",
        )
        user.status = "active"
        await s.commit()
        token, _ = create_access_token(user.id, "member")
    return bearer(token)


async def add_offer(company: Company, **kw: Any) -> uuid.UUID:
    async with SessionLocal() as s:
        o = Offer(org_id=uuid.UUID(company.org_id), status="published", **kw)
        s.add(o)
        await s.commit()
        return o.id


async def add_need(company: Company, **kw: Any) -> uuid.UUID:
    async with SessionLocal() as s:
        n = PurchaseNeed(org_id=uuid.UUID(company.org_id), **kw)
        s.add(n)
        await s.commit()
        return n.id

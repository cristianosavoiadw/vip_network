"""Helpers for tests/test_network.py (catalog, discovery, likes, matches, connections)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.modules.notifications.models import Notification
from tests.conftest import PASSWORD, Company, World


async def member(world: World, owner: Company, departments: list[str]) -> dict[str, str]:
    """Adds an active member with these departments and returns their auth headers."""
    from app.modules.auth import service as auth

    email = world.email()
    r = await world.client.post(
        "/api/v1/team/members",
        headers=owner.h,
        json={"email": email, "full_name": "Pessoa Teste", "departments": departments},
    )
    assert r.status_code == 200, r.text
    async with SessionLocal() as s:
        user = await auth.get_by_email(s, email)
        token = await auth.issue_link(s, user, "activate")
        await s.commit()
    r = await world.client.post(
        f"/api/v1/auth/activate/{token}", json={"password": PASSWORD, "password_confirm": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def offer(world: World, c: Company, name: str, **extra: Any) -> dict[str, Any]:
    r = await world.client.post("/api/v1/offers", headers=c.h, json={"name": name, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def need(world: World, c: Company, name: str, **extra: Any) -> dict[str, Any]:
    r = await world.client.post("/api/v1/purchase-needs", headers=c.h, json={"name": name, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def like(
    world: World, c: Company, target: Company, intent: str, products: list[str] | None = None
) -> Any:
    return await world.client.post(
        "/api/v1/likes",
        headers=c.h,
        json={"target_org_id": target.org_id, "intent": intent, "products": products or []},
    )


async def cards(world: World, c: Company, headers: dict[str, str] | None = None) -> list[dict]:
    r = await world.client.get("/api/v1/discovery/cards?limit=100", headers=headers or c.h)
    assert r.status_code == 200, r.text
    return r.json()


def card_of(cards_: list[dict], target: Company) -> dict | None:
    return next((x for x in cards_ if x["id"] == target.org_id), None)


async def notifications(org_id: str, kind: str) -> list[Notification]:
    async with SessionLocal() as s:
        return list(
            (
                await s.execute(
                    select(Notification).where(
                        Notification.org_id == uuid.UUID(org_id), Notification.kind == kind
                    )
                )
            ).scalars()
        )


async def everything_seen_by(world: World, c: Company, other: Company) -> str:
    """Every network response one company can fetch, concatenated (privacy checks)."""
    out = []
    for url in (
        "/api/v1/discovery/cards?limit=100",
        f"/api/v1/companies/{other.slug}",
        "/api/v1/directory",
        "/api/v1/likes?tab=todos&filter=all",
        "/api/v1/likes/summary",
        "/api/v1/matches",
        "/api/v1/matches/unseen",
        "/api/v1/network",
        "/api/v1/connections",
        "/api/v1/discovery/saved",
    ):
        r = await world.client.get(url, headers=c.h)
        assert r.status_code == 200, (url, r.text)
        out.append(json.dumps(r.json(), ensure_ascii=False))
    return "\n".join(out)

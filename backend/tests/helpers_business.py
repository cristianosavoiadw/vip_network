"""Helpers for tests/test_business.py: relations inserted straight in the tables (the likes /
matches / connections APIs are written in parallel) and extra members of a company."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.modules.auth.models import User
from app.modules.connections.models import Connection
from app.modules.discovery.models import OrgBlock
from app.modules.matches.models import Match
from tests.conftest import PASSWORD, Company, World


def _pair(a: str, b: str) -> tuple[uuid.UUID, uuid.UUID]:
    lo, hi = sorted((a, b))
    return uuid.UUID(lo), uuid.UUID(hi)


async def make_match(
    buyer: Company,
    seller: Company,
    *,
    kind: str = "commercial",
    status: str = "MATCH_CONFIRMED",
    origin: str = "MUTUAL_LIKE",
    product: str = "Embalagens térmicas T-500",
    score: int = 92,
) -> str:
    low, high = _pair(buyer.org_id, seller.org_id)
    async with SessionLocal() as s:
        m = Match(
            org_low_id=low,
            org_high_id=high,
            kind=kind,
            status=status,
            origin=origin,
            buyer_org_id=uuid.UUID(buyer.org_id) if kind == "commercial" else None,
            seller_org_id=uuid.UUID(seller.org_id) if kind == "commercial" else None,
            product=product,
            score=score,
            confirmed_at=datetime.now(UTC),
            seen_user_ids=[],
        )
        s.add(m)
        await s.commit()
        return str(m.id)


async def make_connection(a: Company, b: Company, *, status: str = "accepted") -> None:
    low, high = _pair(a.org_id, b.org_id)
    async with SessionLocal() as s:
        s.add(
            Connection(
                org_low_id=low,
                org_high_id=high,
                requested_by_org_id=uuid.UUID(a.org_id),
                status=status,
                source="event",
                accepted_at=datetime.now(UTC) if status == "accepted" else None,
            )
        )
        await s.commit()


async def block(source: Company, target: Company) -> None:
    async with SessionLocal() as s:
        s.add(
            OrgBlock(source_org_id=uuid.UUID(source.org_id), target_org_id=uuid.UUID(target.org_id))
        )
        await s.commit()


async def add_member(
    world: World, company: Company, departments: list[str], name: str = "Paula Reis"
) -> dict[str, str]:
    """An active colleague in ``departments``; returns auth headers."""
    async with SessionLocal() as s:
        u = User(
            email=world.email(),
            password_hash=hash_password(PASSWORD),
            kind="member",
            status="active",
            full_name=name,
            org_id=uuid.UUID(company.org_id),
            is_org_owner=False,
            departments=departments,
        )
        s.add(u)
        await s.commit()
        token, _ = create_access_token(u.id, "member")
    return {"Authorization": f"Bearer {token}"}

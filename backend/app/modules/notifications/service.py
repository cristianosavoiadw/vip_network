"""Notify the right people of an organization about an event (scope §27).

``notify()`` creates one in-platform notification per recipient, pushes it on the WebSocket and
queues the e-mail of the same trigger key (switched off / user preference respected by
``mail.trigger``). Recipients = active members of the organization whose departments match;
the owner always receives.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import realtime
from app.modules.auth.models import User
from app.modules.mail import service as mail
from app.modules.notifications.models import Notification
from app.modules.organizations.models import Organization


async def members(
    session: AsyncSession, org_id: uuid.UUID, departments: Iterable[str] | None = None
) -> list[User]:
    rows = (
        await session.execute(
            select(User).where(
                User.org_id == org_id, User.kind == "member", User.status == "active"
            )
        )
    ).scalars()
    wanted = set(departments) if departments is not None else None
    out = []
    for u in rows:
        if wanted is None or u.is_org_owner or wanted.intersection(u.departments or []):
            out.append(u)
    return out


async def notify(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    kind: str,
    title: str,
    body: str = "",
    link: str = "",
    departments: Iterable[str] | None = None,
    users: Iterable[User] | None = None,
    email_vars: dict[str, Any] | None = None,
    email: bool = True,
    data: dict[str, Any] | None = None,
) -> int:
    recipients = list(users) if users is not None else await members(session, org_id, departments)
    if not recipients:
        return 0
    org = await session.get(Organization, org_id)
    for user in recipients:
        n = Notification(
            user_id=user.id,
            org_id=org_id,
            kind=kind,
            title=title,
            body=body,
            link=link,
            data=data or {},
        )
        session.add(n)
        await session.flush()
        realtime.publish(
            user.id,
            {"type": "notification", "id": str(n.id), "kind": kind, "title": title, "link": link},
        )
        if email:
            await mail.trigger(
                session,
                kind,
                user=user,
                variables={"empresa": org.display_name if org else "", **(email_vars or {})},
                link=link,
            )
    return len(recipients)


async def list_for(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int = 50
) -> list[Notification]:
    return list(
        (
            await session.execute(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


async def mark_read(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> None:
    q = update(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    if ids:
        q = q.where(Notification.id.in_(ids))
    await session.execute(q.values(read_at=datetime.now(UTC)))

"""Connections between companies and the "Minha Rede" groups (scope §11).

One row per pair. A commercial or partnership match creates an accepted connection (source
"match"); a request needs the other company to accept. A block wins over everything: blocked
pairs never show and cannot request.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.modules.auth.deps import Ctx
from app.modules.connections.models import Connection
from app.modules.discovery import service as discovery
from app.modules.likes.models import Like
from app.modules.matches import service as matches
from app.modules.notifications.service import notify
from app.modules.organizations.models import Organization
from app.modules.organizations.views import iso, org_card

RECENT = timedelta(days=30)
SOURCE_LABELS = {"match": "Match", "manual": "Conexão direta", "event": "Evento"}


def pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return matches.pair(a, b)


def other_of(c: Connection, org_id: uuid.UUID) -> uuid.UUID:
    return c.org_high_id if c.org_low_id == org_id else c.org_low_id


async def pair_connection(session: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> Connection | None:
    low, high = pair(a, b)
    return (
        await session.execute(
            select(Connection).where(Connection.org_low_id == low, Connection.org_high_id == high)
        )
    ).scalar_one_or_none()


def connection_brief(c: Connection, org_id: uuid.UUID) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "status": c.status,
        "source": c.source,
        "source_label": SOURCE_LABELS.get(c.source, c.source),
        "requested_by_me": c.requested_by_org_id == org_id,
        "message": c.message,
        "accepted_at": iso(c.accepted_at),
        "created_at": iso(c.created_at),
        "updated_at": iso(c.updated_at),
    }


def connection_view(c: Connection, org_id: uuid.UUID, other: Organization) -> dict[str, Any]:
    return {**connection_brief(c, org_id), "org": org_card(other)}


async def ensure_accepted(
    session: AsyncSession, a: uuid.UUID, b: uuid.UUID, *, source: str, requested_by: uuid.UUID
) -> Connection:
    """Create or turn into an accepted connection (used by matches and events)."""
    c = await pair_connection(session, a, b)
    now = datetime.now(UTC)
    if c is None:
        low, high = pair(a, b)
        c = Connection(
            org_low_id=low,
            org_high_id=high,
            requested_by_org_id=requested_by,
            status="accepted",
            source=source,
            accepted_at=now,
        )
        session.add(c)
    elif c.status != "accepted":
        c.status = "accepted"
        c.source = source
        c.accepted_at = now
    else:
        return c
    await session.flush()
    await discovery.bump_stats(session, a, connections=1)
    await discovery.bump_stats(session, b, connections=1)
    return c


# ------------------------------------------------------------------ actions


async def request(
    session: AsyncSession, ctx: Ctx, target_org_id: uuid.UUID, message: str
) -> Connection:
    target = await discovery.get_target(session, ctx, target_org_id)
    if await discovery.is_blocked(session, ctx.org_id, target.id):
        raise Forbidden("Não é possível se conectar com esta empresa.", code="blocked")
    c = await pair_connection(session, ctx.org_id, target.id)
    if c is not None and c.status == "accepted":
        raise Conflict("As empresas já estão conectadas.", code="already_connected")
    if c is not None and c.status == "requested":
        if c.requested_by_org_id == ctx.org_id:
            return c
        # they had asked us: asking back accepts
        return await accept(session, ctx, c.id)
    if c is None:
        low, high = pair(ctx.org_id, target.id)
        c = Connection(org_low_id=low, org_high_id=high, source="manual")
        session.add(c)
    c.requested_by_org_id = ctx.org_id
    c.status = "requested"
    c.source = "manual"
    c.message = message
    c.accepted_at = None
    await session.flush()
    await notify(
        session,
        target.id,
        kind="connection.request",
        title=f"{ctx.org.display_name} quer se conectar com sua empresa",
        body=message[:200],
        link="/app/rede",
        departments=("diretoria",),
        email_vars={"empresa_origem": ctx.org.display_name},
        data={"connection_id": str(c.id), "org_id": str(ctx.org_id)},
    )
    return c


async def _own(session: AsyncSession, ctx: Ctx, connection_id: uuid.UUID) -> Connection:
    c = await session.get(Connection, connection_id)
    if c is None or ctx.org_id not in (c.org_low_id, c.org_high_id):
        raise NotFound("Conexão não encontrada.", code="connection_not_found")
    if await discovery.is_blocked(session, c.org_low_id, c.org_high_id):
        raise NotFound("Conexão não encontrada.", code="connection_not_found")
    return c


async def accept(session: AsyncSession, ctx: Ctx, connection_id: uuid.UUID) -> Connection:
    c = await _own(session, ctx, connection_id)
    if c.status != "requested" or c.requested_by_org_id == ctx.org_id:
        raise AppError("Este pedido não está aguardando sua resposta.", code="not_pending")
    c.status = "accepted"
    c.accepted_at = datetime.now(UTC)
    await session.flush()
    await discovery.bump_stats(session, c.org_low_id, connections=1)
    await discovery.bump_stats(session, c.org_high_id, connections=1)
    await notify(
        session,
        c.requested_by_org_id,
        kind="connection.accepted",
        title=f"{ctx.org.display_name} aceitou a conexão",
        link="/app/rede",
        departments=("diretoria",),
        email_vars={"empresa_origem": ctx.org.display_name},
        data={"connection_id": str(c.id), "org_id": str(ctx.org_id)},
    )
    return c


async def decline(session: AsyncSession, ctx: Ctx, connection_id: uuid.UUID) -> Connection:
    c = await _own(session, ctx, connection_id)
    if c.status != "requested" or c.requested_by_org_id == ctx.org_id:
        raise AppError("Este pedido não está aguardando sua resposta.", code="not_pending")
    c.status = "declined"
    await session.flush()
    return c


async def end(session: AsyncSession, ctx: Ctx, connection_id: uuid.UUID) -> Connection:
    c = await _own(session, ctx, connection_id)
    if c.status not in ("accepted", "requested"):
        raise AppError("Esta conexão já está encerrada.", code="not_active")
    c.status = "ended"
    await session.flush()
    return c


async def archive(session: AsyncSession, ctx: Ctx, connection_id: uuid.UUID) -> Connection:
    c = await _own(session, ctx, connection_id)
    c.status = "archived"
    await session.flush()
    return c


# ------------------------------------------------------------------ read


async def _connections(
    session: AsyncSession, org_id: uuid.UUID
) -> list[tuple[Connection, Organization]]:
    blocked = await discovery.blocked_ids(session, org_id)
    rows = list(
        (
            await session.execute(
                select(Connection)
                .where(or_(Connection.org_low_id == org_id, Connection.org_high_id == org_id))
                .order_by(Connection.updated_at.desc())
            )
        ).scalars()
    )
    ids = {other_of(c, org_id) for c in rows} - blocked
    if not ids:
        return []
    orgs = {
        o.id: o
        for o in (
            await session.execute(
                select(Organization).where(
                    Organization.id.in_(ids), Organization.status == "active"
                )
            )
        ).scalars()
    }
    return [(c, orgs[other_of(c, org_id)]) for c in rows if other_of(c, org_id) in orgs]


async def list_connections(
    session: AsyncSession, ctx: Ctx, *, status: str | None = None
) -> list[dict[str, Any]]:
    return [
        connection_view(c, ctx.org_id, o)
        for c, o in await _connections(session, ctx.org_id)
        if status is None or c.status == status
    ]


def _item(o: Organization, since: datetime | None, label: str, **extra: Any) -> dict[str, Any]:
    return {"org": org_card(o), "since": iso(since), "label": label, **extra}


async def network(session: AsyncSession, ctx: Ctx) -> dict[str, Any]:
    conns = await _connections(session, ctx.org_id)
    accepted = [(c, o) for c, o in conns if c.status == "accepted"]
    now = datetime.now(UTC)

    recent = [
        _item(o, c.accepted_at, SOURCE_LABELS.get(c.source, c.source), connection_id=str(c.id))
        for c, o in accepted
        if c.accepted_at and now - c.accepted_at <= RECENT
    ]
    recent.sort(key=lambda i: i["since"] or "", reverse=True)
    connected = [
        _item(o, c.accepted_at, SOURCE_LABELS.get(c.source, c.source), connection_id=str(c.id))
        for c, o in accepted
    ]
    events = [
        _item(o, c.accepted_at, "Evento", connection_id=str(c.id))
        for c, o in accepted
        if c.source == "event"
    ]
    pending = [
        _item(o, c.created_at, "Pedido de conexão", connection_id=str(c.id), message=c.message)
        for c, o in conns
        if c.status == "requested" and c.requested_by_org_id != ctx.org_id
    ]

    partners, suppliers, clients = [], [], []
    client_ids: set[uuid.UUID] = set()
    for m, o in await matches.org_matches(session, ctx.org_id):
        if not matches.is_confirmed(m):
            continue
        if m.kind == "partnership":
            partners.append(
                _item(o, m.confirmed_at, "Parceria", match_id=str(m.id), product=m.product)
            )
        elif m.kind == "commercial" and m.buyer_org_id == ctx.org_id:
            suppliers.append(
                _item(o, m.confirmed_at, "Fornecedor", match_id=str(m.id), product=m.product)
            )
        elif m.kind == "commercial" and m.seller_org_id == ctx.org_id:
            clients.append(
                _item(o, m.confirmed_at, "Match: você vende", match_id=str(m.id), product=m.product)
            )
            client_ids.add(o.id)

    if ctx.sees_intent("buy"):  # received buy-likes are sales leads (Comercial)
        blocked = await discovery.blocked_ids(session, ctx.org_id)
        leads = (
            await session.execute(
                select(Like, Organization)
                .join(Organization, Organization.id == Like.source_org_id)
                .where(
                    Like.target_org_id == ctx.org_id,
                    Like.status == "active",
                    Like.intent == "buy",
                    Organization.status == "active",
                )
                .order_by(Like.created_at.desc())
            )
        ).all()
        for lk, o in leads:
            if o.id in blocked or o.id in client_ids:
                continue
            client_ids.add(o.id)
            clients.append(
                _item(
                    o,
                    lk.created_at,
                    "Quer comprar de você",
                    like_id=str(lk.id),
                    product=", ".join(lk.products),
                )
            )

    def group(key: str, title: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
        return {"key": key, "title": title, "count": len(items), "items": items, "empty": empty}

    return {
        "groups": [
            group("recent", "Conexões recentes", recent, "Nenhuma conexão nos últimos 30 dias."),
            group(
                "connected", "Empresas conectadas", connected, "Nenhuma empresa conectada ainda."
            ),
            group(
                "clients",
                "Clientes potenciais",
                clients,
                "Empresas que querem comprar de você aparecem aqui.",
            ),
            group(
                "suppliers",
                "Fornecedores conectados",
                suppliers,
                "Fornecedores aparecem aqui depois de um match de compra.",
            ),
            group(
                "partners",
                "Parceiros comerciais",
                partners,
                "Nenhum parceiro confirmado ainda. Parcerias aparecem aqui depois de um match de "
                "parceria.",
            ),
            group(
                "events", "Contatos de eventos", events, "Conexões feitas em eventos aparecem aqui."
            ),
        ],
        "pending_requests": pending,
    }

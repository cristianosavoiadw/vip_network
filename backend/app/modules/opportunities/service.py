"""Commercial opportunities and their funnel (scope §12, §15).

An opportunity is shared by two organizations (buyer and seller slots; for a partnership both
companies sit in those slots). Each side sees it from its own perspective (``buy``/``sell``/
``part``), picks its own responsible person and keeps its own private note. The realized value
counts only once both companies confirmed the close.

Relation rules (shared with messaging): two organizations can open an opportunity or a
conversation only with a confirmed match or an accepted connection, and never when either one
blocked the other (§23). Matches and connections are read straight from their tables.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Forbidden, NotFound
from app.modules.auth.models import User
from app.modules.connections.models import Connection
from app.modules.discovery.models import OrgBlock
from app.modules.matches.models import Match
from app.modules.notifications import service as notifications
from app.modules.opportunities.models import STAGES, Opportunity, OpportunityNote
from app.modules.organizations.models import Organization
from app.modules.organizations.views import initials, iso, org_card

OPEN_MATCH_STATUSES = ("MATCH_CONFIRMED", "CONNECTION_ACCEPTED", "IN_CONVERSATION")
VIEW_KINDS = ("buy", "sell", "part")

ORIGIN_LABELS = {
    "MUTUAL_LIKE": "Curtida recíproca",
    "AI_RECOMMENDATION": "Recomendação da IA",
    "DIRECT": "Solicitação direta",
    "EVENT": "Evento",
    "REFERRAL": "Indicação",
    "MANUAL": "Conexão direta",
}
STAGE_LABELS = {
    "new": "Novo",
    "contact": "Contato",
    "qualification": "Qualificação",
    "negotiation": "Negociação",
    "proposal": "Proposta",
    "won": "Ganho",
    "lost": "Perdido",
}
# match origin -> opportunity origin
MATCH_ORIGIN_MAP = {
    "MUTUAL_LIKE": "MUTUAL_LIKE",
    "AI_RECOMMENDATION": "AI_RECOMMENDATION",
    "STRATEGIC_MATCH": "AI_RECOMMENDATION",
    "MANUAL_CONNECTION": "MANUAL",
    "EVENT_CONNECTION": "EVENT",
}
CONNECTION_SOURCE_MAP = {"match": "MUTUAL_LIKE", "event": "EVENT", "manual": "MANUAL"}


def now() -> datetime:
    return datetime.now(UTC)


def pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """(low, high) as the match/connection/conversation tables store it."""
    return (a, b) if str(a) < str(b) else (b, a)


def _uuid(value: Any, what: str = "registro") -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise NotFound(f"Não encontramos este {what}.") from exc


# ------------------------------------------------------------------ relation between two orgs


async def is_blocked(session: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> bool:
    row = (
        await session.execute(
            select(OrgBlock.id)
            .where(
                or_(
                    and_(OrgBlock.source_org_id == a, OrgBlock.target_org_id == b),
                    and_(OrgBlock.source_org_id == b, OrgBlock.target_org_id == a),
                )
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def open_match(session: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> Match | None:
    low, high = pair(a, b)
    return (
        await session.execute(
            select(Match).where(
                Match.org_low_id == low,
                Match.org_high_id == high,
                Match.status.in_(OPEN_MATCH_STATUSES),
            )
        )
    ).scalar_one_or_none()


async def accepted_connection(
    session: AsyncSession, a: uuid.UUID, b: uuid.UUID
) -> Connection | None:
    low, high = pair(a, b)
    return (
        await session.execute(
            select(Connection).where(
                Connection.org_low_id == low,
                Connection.org_high_id == high,
                Connection.status == "accepted",
            )
        )
    ).scalar_one_or_none()


async def require_relation(
    session: AsyncSession, org_id: uuid.UUID, target_id: uuid.UUID
) -> tuple[Match | None, Connection | None]:
    """Raise unless the two orgs have a confirmed match or an accepted connection and no block."""
    if org_id == target_id:
        raise AppError("Escolha outra empresa.", code="same_org")
    target = await session.get(Organization, target_id)
    if target is None or target.status != "active":
        raise NotFound("Empresa não encontrada.", code="org_not_found")
    if await is_blocked(session, org_id, target_id):
        raise Forbidden("Não é possível negociar com esta empresa.", code="blocked")
    match = await open_match(session, org_id, target_id)
    conn = await accepted_connection(session, org_id, target_id)
    if match is None and conn is None:
        raise Forbidden(
            "Vocês precisam de um match confirmado ou de uma conexão aceita para negociar.",
            code="no_relation",
        )
    return match, conn


# ------------------------------------------------------------------ lookup and views


def is_party(opp: Opportunity, org_id: uuid.UUID) -> bool:
    return org_id in (opp.buyer_org_id, opp.seller_org_id)


def other_org_id(opp: Opportunity, org_id: uuid.UUID) -> uuid.UUID | None:
    return opp.seller_org_id if opp.buyer_org_id == org_id else opp.buyer_org_id


def view_kind(opp: Opportunity, org_id: uuid.UUID) -> str:
    if opp.kind == "partnership":
        return "part"
    return "buy" if opp.buyer_org_id == org_id else "sell"


def display_number(opp: Opportunity) -> str:
    return f"OP-{opp.number:04d}"


async def get_for(session: AsyncSession, org_id: uuid.UUID, opp_id: Any) -> Opportunity:
    """The opportunity if ``org_id`` is one of its two companies; 404 otherwise."""
    opp = await session.get(Opportunity, _uuid(opp_id, "oportunidade"))
    if opp is None or not is_party(opp, org_id):
        raise NotFound("Não encontramos esta oportunidade.", code="opportunity_not_found")
    return opp


def user_chip(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {"id": str(user.id), "name": user.full_name, "initials": initials(user.full_name)}


def realized_value(opp: Opportunity) -> int | None:
    """Counted in "negócios efetivados" only when both companies confirmed the close (§15)."""
    if opp.stage == "won" and close_confirmed(opp):
        return opp.closed_value_cents
    return None


def close_confirmed(opp: Opportunity) -> bool:
    parties = {str(opp.buyer_org_id), str(opp.seller_org_id)}
    return opp.stage == "won" and parties.issubset(set(opp.close_confirmed_by or []))


async def _orgs(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, Organization]:
    if not ids:
        return {}
    rows = (await session.execute(select(Organization).where(Organization.id.in_(ids)))).scalars()
    return {o.id: o for o in rows}


async def _users(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    rows = (await session.execute(select(User).where(User.id.in_(ids)))).scalars()
    return {u.id: u for u in rows}


def _owner_id(opp: Opportunity, org_id: uuid.UUID) -> uuid.UUID | None:
    raw = (opp.owners or {}).get(str(org_id))
    try:
        return uuid.UUID(raw) if raw else None
    except ValueError:
        return None


def row_view(
    opp: Opportunity,
    org_id: uuid.UUID,
    orgs: dict[uuid.UUID, Organization],
    users: dict[uuid.UUID, User],
) -> dict[str, Any]:
    other_id = other_org_id(opp, org_id)
    other = orgs.get(other_id) if other_id else None
    owner_id = _owner_id(opp, org_id)
    confirmed_by = set(opp.close_confirmed_by or [])
    return {
        "id": str(opp.id),
        "number": display_number(opp),
        "kind": view_kind(opp, org_id),
        "other_org": org_card(other) if other else None,
        "title": opp.title,
        "product": opp.product,
        "compat": opp.compat,
        "origin": opp.origin,
        "origin_label": ORIGIN_LABELS.get(opp.origin, opp.origin),
        "stage": opp.stage,
        "stage_label": STAGE_LABELS.get(opp.stage, opp.stage),
        "value_estimate_cents": opp.value_estimate_cents,
        "next_action": opp.next_action,
        "owner": user_chip(users.get(owner_id)) if owner_id else None,
        "match_id": str(opp.match_id) if opp.match_id else None,
        "closed_value_cents": opp.closed_value_cents,
        "close": {
            "confirmed_by_me": str(org_id) in confirmed_by,
            "confirmed_by_other": bool(other_id) and str(other_id) in confirmed_by,
            "confirmed": close_confirmed(opp),
            "realized_value_cents": realized_value(opp),
        },
        "created_at": iso(opp.created_at),
        "updated_at": iso(opp.updated_at),
    }


async def rows_view(
    session: AsyncSession, opps: list[Opportunity], org_id: uuid.UUID
) -> list[dict[str, Any]]:
    org_ids = {i for o in opps for i in (o.buyer_org_id, o.seller_org_id) if i}
    owner_ids = {oid for o in opps if (oid := _owner_id(o, org_id))}
    orgs = await _orgs(session, org_ids)
    users = await _users(session, owner_ids)
    return [row_view(o, org_id, orgs, users) for o in opps]


async def detail_view(session: AsyncSession, opp: Opportunity, org_id: uuid.UUID) -> dict[str, Any]:
    out = (await rows_view(session, [opp], org_id))[0]
    note = (
        await session.execute(
            select(OpportunityNote).where(
                OpportunityNote.opportunity_id == opp.id, OpportunityNote.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    out["note"] = note.body if note else ""
    out["note_updated_at"] = iso(note.updated_at) if note else None
    # entries marked for one org (its owner changes) stay inside that org
    out["history"] = [
        {k: v for k, v in h.items() if k != "org_only"}
        for h in (opp.history or [])
        if not h.get("org_only") or h.get("org_only") == str(org_id)
    ]
    from app.modules.messaging.models import Conversation

    conv_id = (
        await session.execute(
            select(Conversation.id)
            .where(Conversation.opportunity_id == opp.id)
            .order_by(Conversation.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    out["conversation_id"] = str(conv_id) if conv_id else None
    return out


def _history(
    opp: Opportunity,
    user: User | None,
    org_id: uuid.UUID | None,
    action: str,
    *,
    before: Any = None,
    after: Any = None,
    org_only: bool = False,
) -> None:
    entry: dict[str, Any] = {
        "at": now().isoformat(),
        "action": action,
        "org_id": str(org_id) if org_id else None,
        "user_id": str(user.id) if user else None,
        "user_name": user.full_name if user else "",
        "from": before,
        "to": after,
    }
    if org_only and org_id:
        entry["org_only"] = str(org_id)
    opp.history = [*(opp.history or []), entry]


# ------------------------------------------------------------------ queries


async def list_for(
    session: AsyncSession, org_id: uuid.UUID, *, kind: str | None = None, stage: str | None = None
) -> list[Opportunity]:
    q = select(Opportunity).where(
        or_(Opportunity.buyer_org_id == org_id, Opportunity.seller_org_id == org_id)
    )
    if stage:
        if stage not in STAGES:
            raise AppError("Etapa inválida.", code="invalid_stage")
        q = q.where(Opportunity.stage == stage)
    if kind == "part":
        q = q.where(Opportunity.kind == "partnership")
    elif kind == "buy":
        q = q.where(Opportunity.kind == "buy_sell", Opportunity.buyer_org_id == org_id)
    elif kind == "sell":
        q = q.where(Opportunity.kind == "buy_sell", Opportunity.seller_org_id == org_id)
    elif kind:
        raise AppError("Tipo inválido.", code="invalid_kind")
    # blocked pairs disappear from the funnel (§23)
    blocked_targets = select(OrgBlock.target_org_id).where(OrgBlock.source_org_id == org_id)
    blocked_sources = select(OrgBlock.source_org_id).where(OrgBlock.target_org_id == org_id)
    for sub in (blocked_targets, blocked_sources):
        q = q.where(
            ~Opportunity.buyer_org_id.in_(sub),
            or_(Opportunity.seller_org_id.is_(None), ~Opportunity.seller_org_id.in_(sub)),
        )
    q = q.order_by(Opportunity.updated_at.desc())
    return list((await session.execute(q)).scalars())


# ------------------------------------------------------------------ writes


async def create(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    user: User,
    target_org_id: uuid.UUID,
    kind: str,
    title: str,
    product: str = "",
    value_estimate_cents: int | None = None,
    next_action: str = "",
) -> Opportunity:
    if kind not in VIEW_KINDS:
        raise AppError("Tipo inválido.", code="invalid_kind")
    match, conn = await require_relation(session, org_id, target_org_id)
    if match is not None:
        origin = MATCH_ORIGIN_MAP.get(match.origin, "MUTUAL_LIKE")
    else:
        origin = CONNECTION_SOURCE_MAP.get(conn.source if conn else "", "MANUAL")
    if kind == "sell":
        buyer, seller = target_org_id, org_id
    else:  # buy, and part (both companies in the two slots)
        buyer, seller = org_id, target_org_id
    opp = Opportunity(
        kind="partnership" if kind == "part" else "buy_sell",
        buyer_org_id=buyer,
        seller_org_id=seller,
        created_by_org_id=org_id,
        match_id=match.id if match else None,
        origin=origin,
        title=title.strip(),
        product=product.strip(),
        compat=match.score if match else None,
        stage="new",
        value_estimate_cents=value_estimate_cents,
        next_action=next_action.strip(),
        owners={str(org_id): str(user.id)},
        history=[],
        close_confirmed_by=[],
    )
    _history(opp, user, org_id, "created", after="new")
    session.add(opp)
    await session.flush()
    await session.refresh(opp)
    return opp


async def from_match(
    session: AsyncSession, *, org_id: uuid.UUID, user: User, match_id: Any
) -> tuple[Opportunity, uuid.UUID, bool]:
    """The opportunity (and conversation) of a confirmed match; created on the first call.
    Returns (opportunity, conversation id, created)."""
    from app.modules.messaging import service as messaging

    match = await session.get(Match, _uuid(match_id, "match"))
    if match is None or org_id not in (match.org_low_id, match.org_high_id):
        raise NotFound("Não encontramos este match.", code="match_not_found")
    other = match.org_high_id if match.org_low_id == org_id else match.org_low_id
    if await is_blocked(session, org_id, other):
        raise Forbidden("Não é possível negociar com esta empresa.", code="blocked")
    if match.status not in OPEN_MATCH_STATUSES:
        raise Forbidden("Este match ainda não foi confirmado.", code="match_not_confirmed")
    opp = (
        await session.execute(
            select(Opportunity)
            .where(Opportunity.match_id == match.id)
            .order_by(Opportunity.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    created = False
    if opp is None:
        orgs = await _orgs(session, {other})
        other_name = orgs[other].display_name if other in orgs else "empresa"
        commercial = match.kind == "commercial" and match.buyer_org_id and match.seller_org_id
        if commercial:
            buyer, seller = match.buyer_org_id, match.seller_org_id
            title = match.product or f"Negócio com {other_name}"
        else:
            buyer, seller = org_id, other
            title = match.product or f"Parceria com {other_name}"
        opp = Opportunity(
            kind="buy_sell" if commercial else "partnership",
            buyer_org_id=buyer,
            seller_org_id=seller,
            created_by_org_id=org_id,
            match_id=match.id,
            origin=MATCH_ORIGIN_MAP.get(match.origin, "MUTUAL_LIKE"),
            title=title[:200],
            product=match.product,
            compat=match.score,
            stage="new",
            owners={str(org_id): str(user.id)},
            history=[],
            close_confirmed_by=[],
        )
        _history(opp, user, org_id, "created", after="new")
        session.add(opp)
        await session.flush()
        await session.refresh(opp)
        created = True
    conv, conv_created = await messaging.get_or_create_for_opportunity(session, opp)
    if conv_created:
        when = (match.confirmed_at or match.created_at or now()).strftime("%d/%m")
        label = ORIGIN_LABELS.get(opp.origin, "")
        await messaging.system_message(session, conv, f"Match confirmado em {when} · {label}")
    if match.status in ("MATCH_CONFIRMED", "CONNECTION_ACCEPTED"):
        match.status = "IN_CONVERSATION"
    return opp, conv.id, created


async def update(
    session: AsyncSession,
    opp: Opportunity,
    *,
    org_id: uuid.UUID,
    user: User,
    fields: dict[str, Any],
) -> Opportunity:
    if "stage" in fields and fields["stage"] is not None and fields["stage"] != opp.stage:
        stage = fields["stage"]
        if stage not in STAGES:
            raise AppError("Etapa inválida.", code="invalid_stage")
        if stage == "won":
            await close(session, opp, org_id=org_id, user=user, won=True)
        elif stage == "lost":
            await close(session, opp, org_id=org_id, user=user, won=False)
        else:
            _history(opp, user, org_id, "stage", before=opp.stage, after=stage)
            opp.stage = stage
            opp.close_confirmed_by = []  # reopened: a new close needs both confirmations again
    if "next_action" in fields and fields["next_action"] is not None:
        value = fields["next_action"].strip()
        if value != opp.next_action:
            _history(opp, user, org_id, "next_action", before=opp.next_action, after=value)
            opp.next_action = value
    if (
        "value_estimate_cents" in fields
        and fields["value_estimate_cents"] != opp.value_estimate_cents
    ):
        value = fields["value_estimate_cents"]
        if value is not None and value < 0:
            raise AppError("Informe um valor positivo.", code="invalid_value")
        _history(opp, user, org_id, "value", before=opp.value_estimate_cents, after=value)
        opp.value_estimate_cents = value
    if fields.get("owner_user_id") is not None:
        owner = await session.get(User, _uuid(fields["owner_user_id"], "usuário"))
        if (
            owner is None
            or owner.org_id != org_id
            or owner.kind != "member"
            or owner.status == "blocked"
        ):
            raise AppError("Escolha uma pessoa da sua empresa.", code="invalid_owner")
        before = (opp.owners or {}).get(str(org_id))
        if before != str(owner.id):
            _history(opp, user, org_id, "owner", before=before, after=str(owner.id), org_only=True)
            opp.owners = {**(opp.owners or {}), str(org_id): str(owner.id)}
    opp.updated_at = now()
    await session.flush()
    return opp


async def close(
    session: AsyncSession,
    opp: Opportunity,
    *,
    org_id: uuid.UUID,
    user: User,
    won: bool,
    value_cents: int | None = None,
) -> Opportunity:
    me = str(org_id)
    if not won:
        _history(opp, user, org_id, "lost", before=opp.stage, after="lost")
        opp.stage = "lost"
        opp.closed_value_cents = None
        opp.close_confirmed_by = []
        opp.updated_at = now()
        await session.flush()
        return opp
    if value_cents is not None and value_cents < 0:
        raise AppError("Informe um valor positivo.", code="invalid_value")
    confirmed = list(opp.close_confirmed_by or []) if opp.stage == "won" else []
    value = value_cents if value_cents is not None else opp.closed_value_cents
    if value is None:
        value = opp.value_estimate_cents
    if confirmed and value != opp.closed_value_cents:
        confirmed = []  # a different value needs a new confirmation from the other side
    if me not in confirmed:
        confirmed.append(me)
    _history(opp, user, org_id, "won", before=opp.stage, after={"value_cents": value})
    first = opp.stage != "won" or len(confirmed) == 1
    opp.stage = "won"
    opp.closed_value_cents = value
    opp.close_confirmed_by = confirmed
    opp.updated_at = now()
    await session.flush()
    other = other_org_id(opp, org_id)
    if first and other is not None and not close_confirmed(opp):
        await notifications.notify(
            session,
            other,
            kind="opportunity.close",
            title=f"Confirme o fechamento de {display_number(opp)} · {opp.title}",
            link=f"/app/oportunidades?op={opp.id}",
            departments=("diretoria", "comercial", "compras"),
            email=False,
        )
    return opp


async def put_note(
    session: AsyncSession, opp: Opportunity, *, org_id: uuid.UUID, body: str
) -> OpportunityNote:
    note = (
        await session.execute(
            select(OpportunityNote).where(
                OpportunityNote.opportunity_id == opp.id, OpportunityNote.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if note is None:
        note = OpportunityNote(opportunity_id=opp.id, org_id=org_id, body=body)
        session.add(note)
    else:
        note.body = body
        note.updated_at = now()
    await session.flush()
    await session.refresh(note)
    return note

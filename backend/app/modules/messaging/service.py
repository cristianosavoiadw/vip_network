"""Business conversations between two organizations (scope §12, §27).

One conversation per opportunity (separate negotiations stay separate) plus, at most, one general
conversation per pair without an opportunity. Readers = active members of the two companies who
reach the "messages" area, narrowed by the conversation ``departments`` map when the company set
one for itself. A block between the two companies closes the conversation (§23).

``tick_forever`` e-mails ``message.new`` to people with messages unread for 30+ minutes, at most
once per conversation per hour per person. The marker is an ``AuditLog`` row
(action ``message.mailed``) holding the time covered in ``data.upto``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import realtime
from app.core.errors import AppError, Forbidden, NotFound
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User
from app.modules.mail import service as mail
from app.modules.messaging.models import Conversation, ConversationRead, Message
from app.modules.notifications import service as notifications
from app.modules.opportunities import service as opps
from app.modules.opportunities.models import Opportunity, OpportunityNote
from app.modules.organizations import permissions
from app.modules.organizations.models import Department, Organization
from app.modules.organizations.views import iso, org_card

log = logging.getLogger(__name__)

KINDS = ("text", "proposal_request", "meeting", "decision", "attachment", "product")
TICK_SECONDS = 300
UNREAD_MAIL_AFTER = timedelta(minutes=30)
MAIL_EVERY = timedelta(hours=1)
MAIL_LOOKBACK = timedelta(days=3)
MAIL_MARKER = "message.mailed"
DEPT_NAMES = dict(permissions.BUILTIN_DEPARTMENTS)


def now() -> datetime:
    return datetime.now(UTC)


def other_org(conv: Conversation, org_id: uuid.UUID) -> uuid.UUID:
    return conv.org_high_id if conv.org_low_id == org_id else conv.org_low_id


def is_party(conv: Conversation, org_id: uuid.UUID) -> bool:
    return org_id in (conv.org_low_id, conv.org_high_id)


def can_read(conv: Conversation, user: User) -> bool:
    """Member of one of the two companies, reaches "messages" and, when the company narrowed
    the conversation to some departments, is in one of them (the owner always reads)."""
    if user.kind != "member" or user.status != "active" or user.org_id is None:
        return False
    if not is_party(conv, user.org_id):
        return False
    if not permissions.can(user.departments or [], "messages", is_owner=user.is_org_owner):
        return False
    allowed = (conv.departments or {}).get(str(user.org_id))
    if allowed and not user.is_org_owner:
        return bool(set(allowed).intersection(user.departments or []))
    return True


async def readers(session: AsyncSession, conv: Conversation) -> list[User]:
    rows = (
        await session.execute(
            select(User).where(
                User.org_id.in_((conv.org_low_id, conv.org_high_id)),
                User.kind == "member",
                User.status == "active",
            )
        )
    ).scalars()
    return [u for u in rows if can_read(conv, u)]


async def get_for(session: AsyncSession, user: User, conv_id: Any) -> Conversation:
    try:
        cid = conv_id if isinstance(conv_id, uuid.UUID) else uuid.UUID(str(conv_id))
    except ValueError as exc:
        raise NotFound("Não encontramos esta conversa.", code="conversation_not_found") from exc
    conv = await session.get(Conversation, cid)
    if conv is None or user.org_id is None or not is_party(conv, user.org_id):
        raise NotFound("Não encontramos esta conversa.", code="conversation_not_found")
    if not can_read(conv, user):
        raise Forbidden("Seu departamento não participa desta conversa.", code="not_participant")
    await ensure_not_blocked(session, conv)
    return conv


async def ensure_not_blocked(session: AsyncSession, conv: Conversation) -> None:
    if await opps.is_blocked(session, conv.org_low_id, conv.org_high_id):
        raise Forbidden("Não é possível conversar com esta empresa.", code="blocked")


# ------------------------------------------------------------------ create


async def get_or_create_for_opportunity(
    session: AsyncSession, opp: Opportunity, *, title: str = ""
) -> tuple[Conversation, bool]:
    conv = (
        await session.execute(
            select(Conversation)
            .where(Conversation.opportunity_id == opp.id)
            .order_by(Conversation.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if conv is not None:
        return conv, False
    if opp.seller_org_id is None:
        raise AppError("Esta oportunidade não tem outra empresa.", code="no_counterpart")
    low, high = opps.pair(opp.buyer_org_id, opp.seller_org_id)
    conv = Conversation(
        org_low_id=low,
        org_high_id=high,
        opportunity_id=opp.id,
        title=(title or opp.title)[:200],
        departments={},
    )
    session.add(conv)
    await session.flush()
    await session.refresh(conv)
    return conv, True


async def start(
    session: AsyncSession,
    *,
    user: User,
    org_id: uuid.UUID,
    target_org_id: uuid.UUID,
    opportunity_id: uuid.UUID | None = None,
    title: str = "",
) -> tuple[Conversation, bool]:
    match, conn = await opps.require_relation(session, org_id, target_org_id)
    if opportunity_id is not None:
        opp = await opps.get_for(session, org_id, opportunity_id)
        if opps.other_org_id(opp, org_id) != target_org_id:
            raise AppError("Esta oportunidade é com outra empresa.", code="opportunity_other_org")
        conv, created = await get_or_create_for_opportunity(session, opp, title=title)
    else:
        low, high = opps.pair(org_id, target_org_id)
        conv = (
            await session.execute(
                select(Conversation)
                .where(
                    Conversation.org_low_id == low,
                    Conversation.org_high_id == high,
                    Conversation.opportunity_id.is_(None),
                )
                .order_by(Conversation.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        created = conv is None
        if conv is None:
            conv = Conversation(
                org_low_id=low,
                org_high_id=high,
                title=title.strip()[:200],
                departments={},
            )
            session.add(conv)
            await session.flush()
            await session.refresh(conv)
    if created:
        if match is not None:
            when = (match.confirmed_at or match.created_at).strftime("%d/%m")
            text = f"Match confirmado em {when}"
        else:
            when = (conn.accepted_at or conn.created_at).strftime("%d/%m") if conn else ""
            text = f"Conexão aceita em {when}"
        await system_message(session, conv, text)
    if match is not None and match.status in ("MATCH_CONFIRMED", "CONNECTION_ACCEPTED"):
        match.status = "IN_CONVERSATION"
    return conv, created


async def system_message(session: AsyncSession, conv: Conversation, body: str) -> Message:
    msg = Message(conversation_id=conv.id, kind="system", body=body, data={})
    session.add(msg)
    await session.flush()
    await session.refresh(msg)
    conv.last_message_at = msg.created_at
    return msg


async def set_departments(
    session: AsyncSession, conv: Conversation, *, org_id: uuid.UUID, departments: list[str]
) -> Conversation:
    """The company narrows who reads this conversation on its side (empty = everyone with
    access to Mensagens)."""
    slugs = sorted(set(departments))
    if slugs:
        known = set(
            (
                await session.execute(select(Department.slug).where(Department.org_id == org_id))
            ).scalars()
        )
        if not set(slugs).issubset(known):
            raise AppError("Departamento desconhecido.", code="invalid_department")
    mapping = dict(conv.departments or {})
    if slugs:
        mapping[str(org_id)] = slugs
    else:
        mapping.pop(str(org_id), None)
    conv.departments = mapping
    await session.flush()
    return conv


# ------------------------------------------------------------------ views


async def _dept_names(session: AsyncSession, org_ids: set[uuid.UUID]) -> dict[tuple[str, str], str]:
    rows = (
        await session.execute(
            select(Department.org_id, Department.slug, Department.name).where(
                Department.org_id.in_(org_ids)
            )
        )
    ).all()
    return {(str(o), s): n for o, s, n in rows}


def _dept_label(user: User | None, names: dict[tuple[str, str], str]) -> str:
    if user is None:
        return ""
    depts = user.departments or []
    if not depts:
        return DEPT_NAMES["diretoria"].split(" /")[0] if user.is_org_owner else ""
    slug = "diretoria" if "diretoria" in depts else depts[0]
    name = names.get((str(user.org_id), slug)) or DEPT_NAMES.get(slug, slug)
    return name.split(" /")[0]


def message_view(
    msg: Message,
    viewer_org_id: uuid.UUID,
    users: dict[uuid.UUID, User],
    orgs: dict[uuid.UUID, Organization],
    names: dict[tuple[str, str], str],
) -> dict[str, Any]:
    sender = None
    if msg.sender_org_id is not None:
        user = users.get(msg.sender_user_id) if msg.sender_user_id else None
        org = orgs.get(msg.sender_org_id)
        sender = {
            "user_id": str(user.id) if user else None,
            "name": user.full_name if user else "",
            "department": _dept_label(user, names),
            "org": {"id": str(org.id), "name": org.display_name} if org else None,
        }
    return {
        "id": str(msg.id),
        "conversation_id": str(msg.conversation_id),
        "kind": msg.kind,
        "body": msg.body,
        "data": msg.data or {},
        "mine": msg.sender_org_id == viewer_org_id,
        "sender": sender,
        "created_at": iso(msg.created_at),
    }


async def messages_view(
    session: AsyncSession, msgs: list[Message], viewer_org_id: uuid.UUID
) -> list[dict[str, Any]]:
    user_ids = {m.sender_user_id for m in msgs if m.sender_user_id}
    org_ids = {m.sender_org_id for m in msgs if m.sender_org_id}
    users = (
        {
            u.id: u
            for u in (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars()
        }
        if user_ids
        else {}
    )
    orgs = (
        {
            o.id: o
            for o in (
                await session.execute(select(Organization).where(Organization.id.in_(org_ids)))
            ).scalars()
        }
        if org_ids
        else {}
    )
    names = await _dept_names(session, org_ids) if org_ids else {}
    return [message_view(m, viewer_org_id, users, orgs, names) for m in msgs]


def preview(msg: Message | None) -> str:
    if msg is None:
        return ""
    body = (msg.body or "").strip()
    data = msg.data or {}
    if msg.kind == "attachment":
        return f"Anexo: {data.get('name', '')}".strip()
    if msg.kind == "proposal_request":
        return f"Solicitação de proposta{': ' + body if body else ''}"
    if msg.kind == "meeting":
        return f"Convite para reunião{': ' + body if body else ''}"
    if msg.kind == "decision":
        return f"Decisão registrada: {body}"
    if msg.kind == "product":
        return f"Produto: {data.get('name') or body}"
    return body[:200]


async def _unread_counts(
    session: AsyncSession, user: User, conv_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not conv_ids:
        return {}
    read = (
        select(ConversationRead.conversation_id, ConversationRead.last_read_at)
        .where(ConversationRead.user_id == user.id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Message.conversation_id, func.count())
            .select_from(Message)
            .outerjoin(read, read.c.conversation_id == Message.conversation_id)
            .where(
                Message.conversation_id.in_(conv_ids),
                Message.sender_org_id.is_not(None),
                Message.sender_org_id != user.org_id,
                or_(read.c.last_read_at.is_(None), Message.created_at > read.c.last_read_at),
            )
            .group_by(Message.conversation_id)
        )
    ).all()
    return {cid: int(n) for cid, n in rows}


async def _last_messages(
    session: AsyncSession, conv_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Message]:
    if not conv_ids:
        return {}
    rows = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id.in_(conv_ids))
            .ext(distinct_on(Message.conversation_id))
            .order_by(Message.conversation_id, Message.created_at.desc(), Message.id.desc())
        )
    ).scalars()
    return {m.conversation_id: m for m in rows}


def _opp_summary(opp: Opportunity | None, org_id: uuid.UUID) -> dict[str, Any] | None:
    if opp is None:
        return None
    return {
        "id": str(opp.id),
        "number": opps.display_number(opp),
        "title": opp.title,
        "kind": opps.view_kind(opp, org_id),
        "stage": opp.stage,
        "stage_label": opps.STAGE_LABELS.get(opp.stage, opp.stage),
    }


async def list_for(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    org_id = user.org_id
    assert org_id is not None
    convs = [
        c
        for c in (
            await session.execute(
                select(Conversation)
                .where(or_(Conversation.org_low_id == org_id, Conversation.org_high_id == org_id))
                .order_by(
                    Conversation.last_message_at.desc().nulls_last(),
                    Conversation.created_at.desc(),
                )
            )
        ).scalars()
        if can_read(c, user)
    ]
    if not convs:
        return []
    others = {other_org(c, org_id) for c in convs}
    blocked = await _blocked_with(session, org_id, others)
    convs = [c for c in convs if other_org(c, org_id) not in blocked]
    ids = [c.id for c in convs]
    orgs = {
        o.id: o
        for o in (
            await session.execute(select(Organization).where(Organization.id.in_(others)))
        ).scalars()
    }
    opp_ids = {c.opportunity_id for c in convs if c.opportunity_id}
    opp_rows = (
        {
            o.id: o
            for o in (
                await session.execute(select(Opportunity).where(Opportunity.id.in_(opp_ids)))
            ).scalars()
        }
        if opp_ids
        else {}
    )
    unread = await _unread_counts(session, user, ids)
    last = await _last_messages(session, ids)
    out = []
    for c in convs:
        other = orgs.get(other_org(c, org_id))
        lm = last.get(c.id)
        out.append(
            {
                "id": str(c.id),
                "title": c.title,
                "other_org": org_card(other) if other else None,
                "opportunity": _opp_summary(opp_rows.get(c.opportunity_id), org_id)
                if c.opportunity_id
                else None,
                "last_message": {
                    "kind": lm.kind,
                    "preview": preview(lm),
                    "mine": lm.sender_org_id == org_id,
                    "created_at": iso(lm.created_at),
                }
                if lm
                else None,
                "unread": unread.get(c.id, 0),
                "last_message_at": iso(c.last_message_at),
            }
        )
    return out


async def _blocked_with(
    session: AsyncSession, org_id: uuid.UUID, others: set[uuid.UUID]
) -> set[uuid.UUID]:
    from app.modules.discovery.models import OrgBlock

    if not others:
        return set()
    rows = (
        await session.execute(
            select(OrgBlock.source_org_id, OrgBlock.target_org_id).where(
                or_(
                    and_(OrgBlock.source_org_id == org_id, OrgBlock.target_org_id.in_(others)),
                    and_(OrgBlock.target_org_id == org_id, OrgBlock.source_org_id.in_(others)),
                )
            )
        )
    ).all()
    return {t if s == org_id else s for s, t in rows}


async def participants(
    session: AsyncSession, conv: Conversation, org_id: uuid.UUID
) -> list[dict[str, str]]:
    allowed = (conv.departments or {}).get(str(org_id))
    names = await _dept_names(session, {org_id})
    if allowed:
        slugs = list(allowed)
    else:
        slugs = [s for s in permissions.AREAS["messages"]]
    return [
        {"slug": s, "name": (names.get((str(org_id), s)) or DEPT_NAMES.get(s, s)).split(" /")[0]}
        for s in slugs
    ]


async def detail(session: AsyncSession, conv: Conversation, user: User) -> dict[str, Any]:
    org_id = user.org_id
    assert org_id is not None
    other_id = other_org(conv, org_id)
    other = await session.get(Organization, other_id)
    opp = await session.get(Opportunity, conv.opportunity_id) if conv.opportunity_id else None
    note = ""
    if opp is not None:
        row = (
            await session.execute(
                select(OpportunityNote).where(
                    OpportunityNote.opportunity_id == opp.id, OpportunityNote.org_id == org_id
                )
            )
        ).scalar_one_or_none()
        note = row.body if row else ""
    decisions = list(
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv.id, Message.kind == "decision")
                .order_by(Message.created_at)
            )
        ).scalars()
    )
    unread = (await _unread_counts(session, user, [conv.id])).get(conv.id, 0)
    opp_out = None
    if opp is not None:
        opp_out = {
            **(_opp_summary(opp, org_id) or {}),
            "value_estimate_cents": opp.value_estimate_cents,
            "next_action": opp.next_action,
            "origin_label": opps.ORIGIN_LABELS.get(opp.origin, opp.origin),
        }
    return {
        "id": str(conv.id),
        "title": conv.title,
        "other_org": org_card(other) if other else None,
        "opportunity": opp_out,
        "participants": {
            "mine": await participants(session, conv, org_id),
            "other": await participants(session, conv, other_id),
        },
        "note": note,
        "decisions": await messages_view(session, decisions, org_id),
        "unread": unread,
        "last_message_at": iso(conv.last_message_at),
        "created_at": iso(conv.created_at),
    }


async def page(
    session: AsyncSession, conv: Conversation, *, before: str | None, limit: int
) -> tuple[list[Message], bool]:
    """Newest ``limit`` messages older than ``before`` (a message id or an ISO date),
    returned oldest first."""
    q = select(Message).where(Message.conversation_id == conv.id)
    if before:
        cursor: Message | None = None
        try:
            cursor = await session.get(Message, uuid.UUID(before))
        except ValueError:
            cursor = None
        if cursor is not None and cursor.conversation_id == conv.id:
            q = q.where(
                or_(
                    Message.created_at < cursor.created_at,
                    and_(Message.created_at == cursor.created_at, Message.id < cursor.id),
                )
            )
        else:
            try:
                dt = datetime.fromisoformat(before.replace("Z", "+00:00"))
            except ValueError as exc:
                raise AppError("Cursor inválido.", code="invalid_cursor") from exc
            q = q.where(Message.created_at < dt)
    rows = list(
        (
            await session.execute(
                q.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
            )
        ).scalars()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    rows.reverse()
    return rows, has_more


# ------------------------------------------------------------------ send / read


async def mark_read(session: AsyncSession, conv: Conversation, user: User) -> datetime:
    """Read up to the database clock (the same clock that stamps ``Message.created_at``)."""
    stmt = pg_insert(ConversationRead).values(
        id=uuid.uuid4(), conversation_id=conv.id, user_id=user.id, last_read_at=func.now()
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_conv_reads", set_={"last_read_at": func.now(), "updated_at": func.now()}
    ).returning(ConversationRead.last_read_at)
    return (await session.execute(stmt)).scalar_one()


def _clean_data(kind: str, data: dict[str, Any], body: str) -> dict[str, Any]:
    if kind == "text":
        if not body.strip():
            raise AppError("Escreva uma mensagem.", code="empty_message")
        return {}
    if kind == "decision" and not body.strip():
        raise AppError("Descreva a decisão.", code="empty_message")
    if kind == "meeting":
        keep = ("starts_at", "ends_at", "duration_minutes", "location", "link", "participants")
        return {k: data[k] for k in keep if k in data}
    if kind == "product":
        keep = ("product_id", "name", "category", "url")
        out = {k: data[k] for k in keep if k in data}
        if not (out.get("name") or body.strip()):
            raise AppError("Informe o produto.", code="empty_message")
        return out
    if kind == "proposal_request":
        keep = ("product", "quantity", "deadline", "details")
        return {k: data[k] for k in keep if k in data}
    return {}


async def send(
    session: AsyncSession,
    conv: Conversation,
    user: User,
    *,
    kind: str,
    body: str = "",
    data: dict[str, Any] | None = None,
) -> Message:
    from app.modules.messaging import uploads

    if kind not in KINDS:
        raise AppError("Tipo de mensagem inválido.", code="invalid_kind")
    await ensure_not_blocked(session, conv)
    org_id = user.org_id
    assert org_id is not None
    data = dict(data or {})
    if kind == "attachment":
        meta = await uploads.read_meta(session, org_id, data.get("upload_id"))
        if meta is None:
            raise AppError("Envie o arquivo antes de anexar.", code="upload_not_found")
        clean = {
            "upload_id": meta["id"],
            "name": meta["name"],
            "size": meta["size"],
            "mime": meta["mime"],
            "url": f"/api/v1/uploads/{meta['id']}",
        }
    else:
        clean = _clean_data(kind, data, body)
    msg = Message(
        conversation_id=conv.id,
        sender_org_id=org_id,
        sender_user_id=user.id,
        kind=kind,
        body=body.strip(),
        data=clean,
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)
    conv.last_message_at = msg.created_at
    await mark_read(session, conv, user)
    await _push(session, conv, msg)
    if kind == "proposal_request":
        await _notify_proposal(session, conv, user)
    return msg


async def _push(session: AsyncSession, conv: Conversation, msg: Message) -> None:
    views: dict[uuid.UUID, dict[str, Any]] = {}
    for reader in await readers(session, conv):
        org_id = reader.org_id
        assert org_id is not None
        if org_id not in views:
            views[org_id] = (await messages_view(session, [msg], org_id))[0]
        realtime.publish(
            reader.id,
            {"type": "message", "conversation_id": str(conv.id), "message": views[org_id]},
        )


async def _notify_proposal(session: AsyncSession, conv: Conversation, user: User) -> None:
    org_id = user.org_id
    assert org_id is not None
    target = other_org(conv, org_id)
    sender_org = await session.get(Organization, org_id)
    opp = await session.get(Opportunity, conv.opportunity_id) if conv.opportunity_id else None
    title = opp.title if opp else conv.title
    recipients = [u for u in await readers(session, conv) if u.org_id == target]
    owner_id = (opp.owners or {}).get(str(target)) if opp else None
    owner = [u for u in recipients if str(u.id) == owner_id]
    if owner:
        recipients = owner
    else:
        business = set(permissions.BUSINESS)
        recipients = [
            u for u in recipients if u.is_org_owner or business.intersection(u.departments or [])
        ]
    if not recipients:
        return
    origin = sender_org.display_name if sender_org else ""
    await notifications.notify(
        session,
        target,
        kind="proposal.received",
        title=f"{origin} pediu uma proposta",
        body=title,
        link=f"/app/mensagens/{conv.id}",
        users=recipients,
        email_vars={"empresa_origem": origin, "titulo": title},
        data={"conversation_id": str(conv.id)},
    )


# ------------------------------------------------------------------ unread e-mails


async def tick(session: AsyncSession, *, at: datetime | None = None) -> int:
    """E-mail ``message.new`` for messages unread for 30+ minutes. Returns e-mails queued."""
    at = at or now()
    cutoff = at - UNREAD_MAIL_AFTER
    since = at - MAIL_LOOKBACK
    conv_ids = list(
        (
            await session.execute(
                select(Message.conversation_id)
                .where(
                    Message.sender_org_id.is_not(None),
                    Message.created_at > since,
                    Message.created_at <= cutoff,
                )
                .distinct()
            )
        ).scalars()
    )
    queued = 0
    for conv_id in conv_ids:
        conv = await session.get(Conversation, conv_id)
        if conv is None:
            continue
        if await opps.is_blocked(session, conv.org_low_id, conv.org_high_id):
            continue
        for user in await readers(session, conv):
            if await _mail_unread(session, conv, user, at=at, cutoff=cutoff, since=since):
                queued += 1
    return queued


async def _mail_unread(
    session: AsyncSession,
    conv: Conversation,
    user: User,
    *,
    at: datetime,
    cutoff: datetime,
    since: datetime,
) -> bool:
    marker = (
        await session.execute(
            select(AuditLog)
            .where(
                AuditLog.action == MAIL_MARKER,
                AuditLog.target_type == "conversation",
                AuditLog.target_id == str(conv.id),
                AuditLog.actor_user_id == user.id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if marker is not None and marker.created_at > at - MAIL_EVERY:
        return False
    floor = since
    if marker is not None:
        try:
            floor = max(floor, datetime.fromisoformat(marker.data.get("upto", "")))
        except ValueError:
            floor = max(floor, marker.created_at)
    last_read = (
        await session.execute(
            select(ConversationRead.last_read_at).where(
                ConversationRead.conversation_id == conv.id, ConversationRead.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if last_read is not None:
        floor = max(floor, last_read)
    count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Message)
                .where(
                    Message.conversation_id == conv.id,
                    Message.sender_org_id.is_not(None),
                    Message.sender_org_id != user.org_id,
                    Message.created_at > floor,
                    Message.created_at <= cutoff,
                )
            )
        ).scalar_one()
    )
    if not count:
        return False
    assert user.org_id is not None
    mine = await session.get(Organization, user.org_id)
    other = await session.get(Organization, other_org(conv, user.org_id))
    opp = await session.get(Opportunity, conv.opportunity_id) if conv.opportunity_id else None
    await mail.trigger(
        session,
        "message.new",
        user=user,
        variables={
            "empresa": mine.display_name if mine else "",
            "empresa_origem": other.display_name if other else "",
            "titulo": opp.title if opp else conv.title,
        },
        link=f"/app/mensagens/{conv.id}",
    )
    session.add(
        AuditLog(
            actor_user_id=user.id,
            org_id=user.org_id,
            action=MAIL_MARKER,
            target_type="conversation",
            target_id=str(conv.id),
            data={"upto": cutoff.isoformat(), "count": count},
            created_at=at,
            updated_at=at,
        )
    )
    await session.flush()
    return True


async def tick_forever() -> None:
    from app.db.session import SessionLocal

    while True:
        try:
            async with SessionLocal() as session:
                await tick(session)
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("messaging tick failed")
        await asyncio.sleep(TICK_SECONDS)

"""Team panel (scope §26): Visão geral, Assinaturas, Rede, Matchmaking, Suporte e moderação and
the VIP Network staff. Least privilege: the team never reads what a company buys
(``purchase_needs``), mentorship content or private opportunity notes.

Brilhar, Eventos, Mentoria and Agentes WeOS screens belong to their own modules.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.modules.analytics import service as metrics
from app.modules.analytics.service import count, rate
from app.modules.audit.models import AuditLog
from app.modules.auth import service as auth
from app.modules.auth.models import User
from app.modules.billing.entitlement import state_label
from app.modules.billing.models import PRICES_CENTS, Invoice, Subscription
from app.modules.boosts.models import BoostCampaign, OrgDayStat
from app.modules.catalog.models import Offer
from app.modules.connections.models import Connection
from app.modules.discovery.models import OrgBlock, Report
from app.modules.integrations.cnpj.validation import format_cnpj, only_digits
from app.modules.intelligence.models import Recommendation
from app.modules.invites.models import Invite
from app.modules.likes.models import Like
from app.modules.mail import service as mail
from app.modules.mail.models import EmailMessage
from app.modules.matches.models import Match
from app.modules.messaging.models import Conversation, Message
from app.modules.opportunities.models import Opportunity
from app.modules.organizations.models import AccessRequest, Organization
from app.modules.organizations.views import iso, org_card, org_private, subscription_view
from app.modules.weos.models import AIJob

# a match that the two companies confirmed (mutual interests are counted apart)
MATCHED = ("MATCH_CONFIRMED", "CONNECTION_ACCEPTED", "IN_CONVERSATION")
OPEN_STAGES = ("contact", "qualification", "negotiation", "proposal")
NEGOTIATION_STAGES = ("negotiation", "proposal", "won")
ORIGIN_LABELS = {
    "MUTUAL_LIKE": "Curtida recíproca",
    "AI_RECOMMENDATION": "Recomendação da IA",
    "EVENT_CONNECTION": "Evento",
    "MANUAL_CONNECTION": "Conexão direta",
    "STRATEGIC_MATCH": "Match estratégico",
}
ADMIN_ROLES = ("owner", "admin", "viewer")
ROLE_LABELS = {"owner": "Proprietário", "admin": "Administrador", "viewer": "Somente leitura"}
PER_PAGE = 50


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def fmt_date(dt: datetime | None) -> str:
    return dt.astimezone(metrics.SP).strftime("%d/%m/%Y") if dt else ""


async def audit(
    session: AsyncSession,
    admin: User | None,
    action: str,
    *,
    org_id: uuid.UUID | None = None,
    target_type: str = "",
    target_id: str = "",
    data: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=admin.id if admin else None,
            org_id=org_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            data=data or {},
            ip=ip,
        )
    )


def _pair_has_match():  # noqa: ANN202
    return exists().where(
        Match.status != "BLOCKED",
        or_(
            and_(Match.org_low_id == Like.source_org_id, Match.org_high_id == Like.target_org_id),
            and_(Match.org_low_id == Like.target_org_id, Match.org_high_id == Like.source_org_id),
        ),
    )


async def reciprocity(session: AsyncSession, since: datetime) -> dict[str, Any]:
    """Likes sent in the window that turned into a reciprocal interest (match row)."""
    row = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(case((_pair_has_match(), 1), else_=0)), 0),
            ).where(Like.created_at >= since, Like.status != "withdrawn")
        )
    ).one()
    likes, matched = int(row[0]), int(row[1])
    return {"likes": likes, "matched": matched, "rate": rate(matched, likes)}


# ------------------------------------------------------------------ Visão geral


async def _today_vs_avg(session: AsyncSession, col: Any, *where: Any) -> tuple[int, float]:
    d0 = metrics.day_start(metrics.now())
    base = select(func.count()).select_from(col.class_).where(*where)
    today = await count(session, base.where(col >= d0))
    prev = await count(session, base.where(col >= d0 - timedelta(days=30), col < d0))
    return today, round(prev / 30, 1)


async def _attention(session: AsyncSession, subs: list[Subscription], at: datetime) -> list[dict]:
    items: list[dict[str, Any]] = []
    past_due = [s for s in subs if s.status == "past_due"]
    if past_due:
        open_cents = await _open_amount(session, past_due)
        items.append(
            {
                "key": "past_due",
                "count": len(past_due),
                "title": plural(len(past_due), "pagamento recusado", "pagamentos recusados"),
                "detail": f"{metrics_brl(open_cents)} em aberto. A Stripe tenta de novo e o "
                "e-mail “Pagamento recusado” já saiu.",
                "section": "subscriptions",
                "severity": "bad",
            }
        )
    reports = await count(
        session, select(func.count()).select_from(Report).where(Report.status == "open")
    )
    if reports:
        items.append(
            {
                "key": "reports",
                "count": reports,
                "title": plural(reports, "denúncia aberta", "denúncias abertas"),
                "detail": "Perfis ou condutas denunciados por outras empresas.",
                "section": "support",
                "severity": "warn",
            }
        )
    requests = await count(
        session,
        select(func.count()).select_from(AccessRequest).where(AccessRequest.status == "pending"),
    )
    if requests:
        items.append(
            {
                "key": "access_requests",
                "count": requests,
                "title": plural(
                    requests, "pedido de acesso a empresa", "pedidos de acesso a empresas"
                ),
                "detail": "CNPJs já cadastrados com novo solicitante esperando o responsável.",
                "section": "support",
                "severity": "warn",
            }
        )
    jobs = (
        await session.execute(
            select(
                AIJob.agent,
                func.count(),
                func.coalesce(func.sum(case((AIJob.status == "dead", 1), else_=0)), 0),
            )
            .where(AIJob.status.in_(("failed", "dead")), AIJob.updated_at >= at - timedelta(days=1))
            .group_by(AIJob.agent)
            .order_by(func.count().desc())
        )
    ).all()
    if jobs:
        total = sum(int(r[1]) for r in jobs)
        dead = sum(int(r[2]) for r in jobs)
        top = jobs[0][0]
        items.append(
            {
                "key": "ai_jobs",
                "count": total,
                "title": f"{top} com falhas" if len(jobs) == 1 else "Agentes WeOS com falhas",
                "detail": f"{plural(total, 'job falhou', 'jobs falharam')} nas últimas 24h; "
                f"{dead} na fila de erro.",
                "section": "agents",
                "severity": "bad",
                "agents": [{"agent": r[0], "failed": int(r[1]), "dead": int(r[2])} for r in jobs],
            }
        )
    expiring = [
        s
        for s in subs
        if metrics.in_vip_period(s, at) and s.vip_until <= at + timedelta(days=30)  # type: ignore[operator]
    ]
    if expiring:
        items.append(
            {
                "key": "vip_expiring",
                "count": len(expiring),
                "title": plural(len(expiring), "Plano VIP vence", "Planos VIP vencem")
                + " em 30 dias",
                "detail": "Os avisos de 30, 15 e 3 dias saem automaticamente.",
                "section": "access",
                "severity": "gold",
            }
        )
    return items


def metrics_brl(cents: int) -> str:
    from app.modules.billing.service import brl

    return brl(cents)


async def _open_amount(session: AsyncSession, subs: list[Subscription]) -> int:
    if not subs:
        return 0
    org_ids = [s.org_id for s in subs]
    open_by_org = dict(
        (
            await session.execute(
                select(Invoice.org_id, func.sum(Invoice.amount_cents))
                .where(Invoice.org_id.in_(org_ids), Invoice.status == "open")
                .group_by(Invoice.org_id)
            )
        ).all()
    )
    return sum(int(open_by_org.get(s.org_id) or PRICES_CENTS[s.plan]) for s in subs)


async def overview(session: AsyncSession) -> dict[str, Any]:
    at = metrics.now()
    m0 = metrics.month_start(at)
    subs = await metrics.all_subscriptions(session)
    paying = [s for s in subs if metrics.is_paying(s, at)]
    mrr = metrics.mrr_cents(subs, at)
    trialing = [s for s in subs if s.status == "trialing" and not metrics.in_vip_period(s, at)]
    vip = [s for s in subs if metrics.in_vip_period(s, at)]
    in_network = await count(
        session,
        select(func.count())
        .select_from(Organization)
        .where(Organization.status.in_(("active", "suspended"))),
    )
    new_month = await count(
        session,
        select(func.count())
        .select_from(Organization)
        .where(Organization.status == "active", Organization.created_at >= m0),
    )
    matches_month = await count(
        session,
        select(func.count())
        .select_from(Match)
        .where(
            Match.status.in_(MATCHED),
            func.coalesce(Match.confirmed_at, Match.created_at) >= m0,
        ),
    )
    negotiations = await count(
        session,
        select(func.count()).select_from(Opportunity).where(Opportunity.stage.in_(OPEN_STAGES)),
    )
    today_rows = []
    for key, label, col, where in (
        ("new_orgs", "Novas empresas", Organization.created_at, ()),
        (
            "trials",
            "Testes iniciados",
            Subscription.trial_start,
            (Subscription.kind == "standard", Subscription.trial_end.is_not(None)),
        ),
        ("invites_accepted", "Convites aceitos", Invite.accepted_at, ()),
        ("likes", "Curtidas", Like.created_at, ()),
        ("matches", "Matches", Match.confirmed_at, (Match.status.in_(MATCHED),)),
        ("messages", "Mensagens", Message.created_at, (Message.kind != "system",)),
        ("emails_sent", "E-mails enviados", EmailMessage.sent_at, ()),
    ):
        today, avg = await _today_vs_avg(session, col, *where)
        today_rows.append({"key": key, "label": label, "today": today, "avg_30d": avg})
    return {
        "kpis": {
            "mrr_cents": mrr,
            "arr_cents": mrr * 12,
            "orgs": {"in_network": in_network, "new_this_month": new_month},
            "paying": {
                "total": len(paying),
                "monthly": sum(1 for s in paying if s.plan == "monthly"),
                "annual": sum(1 for s in paying if s.plan == "annual"),
            },
            "trialing": {
                "total": len(trialing),
                "conversion_90d": metrics.trial_conversion(subs, at, 90),
            },
            "vip": {
                "total": len(vip),
                "expiring_30d": sum(
                    1
                    for s in vip
                    if s.vip_until <= at + timedelta(days=30)  # type: ignore[operator]
                ),
            },
            "matches_month": {
                "total": matches_month,
                "reciprocity": await reciprocity(session, at - timedelta(days=30)),
            },
            "open_negotiations": negotiations,
            "churn": metrics.churn(subs, m0, at),
        },
        "attention": await _attention(session, subs, at),
        "today": today_rows,
    }


# ------------------------------------------------------------------ Assinaturas


def status_label(sub: Subscription, at: datetime) -> str:
    state = state_label(sub, now=at)
    if state == "vip":
        return f"VIP até {fmt_date(sub.vip_until)}"
    if (
        sub.status == "canceled"
        and sub.trial_end
        and sub.canceled_at
        and (sub.canceled_at <= sub.trial_end)
    ):
        return "Cancelada no teste"
    return {
        "trial": "Em teste",
        "active": "Ativa",
        "past_due": "Pagamento recusado",
        "canceled": "Cancelada",
        "expired": "Expirada",
    }.get(state, "Sem assinatura")


def _next_charge(sub: Subscription, at: datetime) -> datetime | None:
    if sub.status == "canceled" or (sub.cancel_at_period_end and sub.status != "trialing"):
        return None
    if metrics.in_vip_period(sub, at):
        return sub.vip_until
    if sub.status == "trialing":
        return sub.trial_end
    return sub.current_period_end


def _amount(sub: Subscription) -> int:
    if (
        sub.status == "canceled"
        and sub.trial_end
        and sub.canceled_at
        and (sub.canceled_at <= sub.trial_end)
    ):
        return 0
    return PRICES_CENTS.get(sub.plan, 0)


async def subscriptions(
    session: AsyncSession, *, status: str | None, kind: str | None, q: str | None
) -> dict[str, Any]:
    at = metrics.now()
    subs = await metrics.all_subscriptions(session)
    stmt = select(Organization, Subscription).join(
        Subscription, Subscription.org_id == Organization.id
    )
    if kind:
        stmt = stmt.where(Subscription.kind == kind)
    if q:
        stmt = stmt.where(_org_search(q))
    rows = []
    for org, sub in (await session.execute(stmt.order_by(Organization.trade_name))).all():
        state = state_label(sub, now=at)
        if status:
            wanted = {status} if status != "canceled" else {"canceled", "expired"}
            if state not in wanted:
                continue
        origin = "invite" if org.entry == "invite" or sub.kind == "vip" else "subscription"
        rows.append(
            {
                "org": org_card(org),
                "cnpj": format_cnpj(org.cnpj),
                "plan": sub.plan,
                "kind": sub.kind,
                "status": sub.status,
                "state": state,
                "status_label": status_label(sub, at),
                "origin": origin,
                "origin_label": "Convite" if origin == "invite" else "Assinatura",
                "next_charge_at": iso(_next_charge(sub, at)),
                "vip_until": iso(sub.vip_until),
                "amount_cents": _amount(sub),
                "card_last4": sub.card_last4,
                "cancel_at_period_end": sub.cancel_at_period_end,
            }
        )
    trialing = [s for s in subs if s.status == "trialing" and not metrics.in_vip_period(s, at)]
    past_due = [s for s in subs if s.status == "past_due"]
    return {
        "kpis": {
            "paying": {
                "total": sum(1 for s in subs if metrics.is_paying(s, at)),
                "mrr_cents": metrics.mrr_cents(subs, at),
            },
            "trialing": {
                "total": len(trialing),
                "ending_7d": sum(
                    1 for s in trialing if s.trial_end and s.trial_end <= at + timedelta(days=7)
                ),
            },
            "past_due": {
                "total": len(past_due),
                "open_cents": await _open_amount(session, past_due),
            },
            "trial_conversion_90d": metrics.trial_conversion(subs, at, 90),
        },
        "items": rows,
    }


# ------------------------------------------------------------------ Rede


def _org_search(q: str):  # noqa: ANN202
    term = f"%{q.strip()}%"
    conds = [Organization.trade_name.ilike(term), Organization.legal_name.ilike(term)]
    digits = only_digits(q)
    if len(digits) >= 4:
        conds.append(Organization.cnpj.contains(digits))
    return or_(*conds)


def _network_status(org: Organization) -> tuple[str, str]:
    if org.status == "suspended":
        return "suspended", "Suspensa"
    if org.status == "pending":
        return "pending", "Cadastro incompleto"
    if not org.verified:
        return "unverified", "Verificação pendente"
    return "active", "Ativa"


def _counts_cols(org_id_col: Any) -> dict[str, Any]:
    return {
        "users": select(func.count(User.id))
        .where(User.org_id == org_id_col, User.kind == "member", User.status != "blocked")
        .scalar_subquery(),
        "likes_sent": select(func.count(Like.id))
        .where(Like.source_org_id == org_id_col, Like.status != "withdrawn")
        .scalar_subquery(),
        "likes_received": select(func.count(Like.id))
        .where(Like.target_org_id == org_id_col, Like.status != "withdrawn")
        .scalar_subquery(),
        "matches": select(func.count(Match.id))
        .where(
            or_(Match.org_low_id == org_id_col, Match.org_high_id == org_id_col),
            Match.status.in_(MATCHED),
        )
        .scalar_subquery(),
    }


async def orgs(
    session: AsyncSession, *, q: str | None, status: str | None, page: int
) -> dict[str, Any]:
    at = metrics.now()
    cols = _counts_cols(Organization.id)
    stmt = select(Organization, *cols.values())
    where = []
    if q:
        where.append(_org_search(q))
    if status == "unverified":
        where += [Organization.status == "active", Organization.verified.is_(False)]
    elif status:
        where.append(Organization.status == status)
    total = await count(session, select(func.count()).select_from(Organization).where(*where))
    page = max(page, 1)
    rows = (
        await session.execute(
            stmt.where(*where)
            .order_by(Organization.trade_name)
            .offset((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )
    ).all()
    items = []
    for org, users, sent, received, matches in rows:
        st, label = _network_status(org)
        items.append(
            {
                "org": org_card(org),
                "cnpj": format_cnpj(org.cnpj),
                "segment": org.segment,
                "sector": org.sector,
                "city": org.city,
                "state": org.state,
                "users": int(users or 0),
                "likes_sent": int(sent or 0),
                "likes_received": int(received or 0),
                "matches": int(matches or 0),
                "status": org.status,
                "network_status": st,
                "status_label": label,
                "verified": org.verified,
                "created_at": iso(org.created_at),
            }
        )
    registered = await count(session, select(func.count()).select_from(Organization))
    active = await count(
        session,
        select(func.count()).select_from(Organization).where(Organization.status == "active"),
    )
    visits = await count(
        session,
        select(func.coalesce(func.sum(OrgDayStat.profile_visits), 0)).where(
            OrgDayStat.day >= (at - timedelta(days=30)).date()
        ),
    )
    connections = await count(
        session,
        select(func.count()).select_from(Connection).where(Connection.status == "accepted"),
    )
    connections_month = await count(
        session,
        select(func.count())
        .select_from(Connection)
        .where(Connection.status == "accepted", Connection.accepted_at >= metrics.month_start(at)),
    )
    unverified = await count(
        session,
        select(func.count())
        .select_from(Organization)
        .where(Organization.status == "active", Organization.verified.is_(False)),
    )
    return {
        "kpis": {
            "active": active,
            "registered": registered,
            "profile_visits_30d": visits,
            "connections": connections,
            "connections_this_month": connections_month,
            "verification_pending": unverified,
        },
        "items": items,
        "page": page,
        "per_page": PER_PAGE,
        "total": total,
    }


async def _get_org(session: AsyncSession, org_id: uuid.UUID) -> Organization:
    org = await session.get(Organization, org_id)
    if org is None:
        raise NotFound("Empresa não encontrada.", code="org_not_found")
    return org


async def org_detail(session: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Everything the team needs to support a company, never what it buys (§26, §5.2)."""
    org = await _get_org(session, org_id)
    sub = (
        await session.execute(select(Subscription).where(Subscription.org_id == org.id))
    ).scalar_one_or_none()
    members = (
        (
            await session.execute(
                select(User)
                .where(User.org_id == org.id, User.kind == "member")
                .order_by(User.is_org_owner.desc(), User.full_name)
            )
        )
        .scalars()
        .all()
    )
    invoices = (
        (
            await session.execute(
                select(Invoice)
                .where(Invoice.org_id == org.id)
                .order_by(Invoice.created_at.desc())
                .limit(12)
            )
        )
        .scalars()
        .all()
    )
    oid = org.id

    def pair(m: Any) -> Any:
        return or_(m.org_low_id == oid, m.org_high_id == oid)

    c = {
        "offers": await count(
            session, select(func.count()).select_from(Offer).where(Offer.org_id == oid)
        ),
        "offers_published": await count(
            session,
            select(func.count())
            .select_from(Offer)
            .where(Offer.org_id == oid, Offer.status == "published"),
        ),
        "likes_sent": await count(
            session,
            select(func.count())
            .select_from(Like)
            .where(Like.source_org_id == oid, Like.status != "withdrawn"),
        ),
        "likes_received": await count(
            session,
            select(func.count())
            .select_from(Like)
            .where(Like.target_org_id == oid, Like.status != "withdrawn"),
        ),
        "matches": await count(
            session,
            select(func.count()).select_from(Match).where(pair(Match), Match.status.in_(MATCHED)),
        ),
        "mutual_interests": await count(
            session,
            select(func.count())
            .select_from(Match)
            .where(pair(Match), Match.status == "MUTUAL_INTEREST"),
        ),
        "connections": await count(
            session,
            select(func.count())
            .select_from(Connection)
            .where(pair(Connection), Connection.status == "accepted"),
        ),
        "opportunities": await count(
            session,
            select(func.count())
            .select_from(Opportunity)
            .where(or_(Opportunity.buyer_org_id == oid, Opportunity.seller_org_id == oid)),
        ),
        "conversations": await count(
            session, select(func.count()).select_from(Conversation).where(pair(Conversation))
        ),
        "reports_received": await count(
            session, select(func.count()).select_from(Report).where(Report.target_org_id == oid)
        ),
        "blocks_received": await count(
            session,
            select(func.count()).select_from(OrgBlock).where(OrgBlock.target_org_id == oid),
        ),
        "boosts_active": await count(
            session,
            select(func.count())
            .select_from(BoostCampaign)
            .where(BoostCampaign.org_id == oid, BoostCampaign.status == "active"),
        ),
    }
    invited_by = (
        await session.get(Organization, org.invited_by_org_id) if org.invited_by_org_id else None
    )
    st, label = _network_status(org)
    return {
        "org": {
            **org_private(org),
            "cnpj": format_cnpj(org.cnpj),
            "network_status": st,
            "status_label": label,
            "created_at": iso(org.created_at),
        },
        "invited_by": org_card(invited_by) if invited_by else None,
        "members": [
            {
                "id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "job_title": u.job_title,
                "departments": u.departments,
                "is_org_owner": u.is_org_owner,
                "status": u.status,
                "last_login_at": iso(u.last_login_at),
            }
            for u in members
        ],
        "subscription": {
            **(subscription_view(sub) or {}),
            "status_label": status_label(sub, metrics.now()),
            "amount_cents": _amount(sub),
        }
        if sub
        else None,
        "invoices": [
            {
                "id": str(i.id),
                "amount_cents": i.amount_cents,
                "status": i.status,
                "description": i.description,
                "paid_at": iso(i.paid_at),
                "period_end": iso(i.period_end),
            }
            for i in invoices
        ],
        "counts": c,
        "privacy": "O que a empresa compra, as notas privadas e a mentoria não aparecem aqui.",
    }


async def set_org_state(
    session: AsyncSession,
    org_id: uuid.UUID,
    action: str,
    admin: User,
    *,
    ip: str | None,
    verified: bool = True,
) -> dict[str, Any]:
    org = await _get_org(session, org_id)
    before = {"status": org.status, "verified": org.verified}
    if action == "suspend":
        if org.status == "suspended":
            raise Conflict("A empresa já está suspensa.", code="already_suspended")
        org.status = "suspended"
        members = (
            (await session.execute(select(User.id).where(User.org_id == org.id))).scalars().all()
        )
        for uid in members:
            await auth.revoke_all(session, uid)
    elif action == "reactivate":
        if org.status != "suspended":
            raise Conflict("A empresa não está suspensa.", code="not_suspended")
        org.status = "active" if org.onboarding_completed_at else "pending"
    elif action == "verify":
        org.verified = verified
    else:
        raise AppError("Ação inválida.", code="invalid_action")
    await audit(
        session,
        admin,
        f"admin.org.{action}",
        org_id=org.id,
        target_type="organization",
        target_id=str(org.id),
        data={"before": before, "after": {"status": org.status, "verified": org.verified}},
        ip=ip,
    )
    await session.flush()
    return await org_detail(session, org.id)


# ------------------------------------------------------------------ Matchmaking


async def matchmaking(session: AsyncSession) -> dict[str, Any]:
    at = metrics.now()
    since90 = at - timedelta(days=90)
    rec = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(case((Recommendation.status == "acted", 1), else_=0)), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                or_(
                                    Recommendation.status == "dismissed",
                                    and_(
                                        Recommendation.status == "new",
                                        Recommendation.created_at < at - timedelta(days=14),
                                    ),
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(Recommendation.created_at >= since90)
        )
    ).one()
    rec_total, accepted, ignored = int(rec[0]), int(rec[1]), int(rec[2])
    false_matches = await count(
        session,
        select(func.count())
        .select_from(Report)
        .where(Report.reason.ilike("%match%"), Report.created_at >= at - timedelta(days=30)),
    )
    negotiated = exists().where(
        Opportunity.match_id == Match.id, Opportunity.stage.in_(NEGOTIATION_STAGES)
    )
    by_origin = dict(
        (r[0], (int(r[1]), int(r[2])))
        for r in (
            await session.execute(
                select(
                    Match.origin,
                    func.count(),
                    func.coalesce(func.sum(case((negotiated, 1), else_=0)), 0),
                )
                .where(Match.status.in_(MATCHED))
                .group_by(Match.origin)
            )
        ).all()
    )
    origins = []
    for key, label in ORIGIN_LABELS.items():
        n, neg = by_origin.get(key, (0, 0))
        origins.append(
            {
                "origin": key,
                "label": label,
                "matches": n,
                "negotiations": neg,
                "negotiation_rate": rate(neg, n),
            }
        )
    sell_sell = await count(
        session, select(func.count()).select_from(Match).where(Match.kind == "mutual_sell")
    )
    no_category = await count(
        session,
        select(func.count())
        .select_from(Offer)
        .where(Offer.category == "", Offer.status != "draft"),
    )
    buy_buy = await count(
        session,
        select(func.count())
        .select_from(Match)
        .where(Match.kind == "mutual_buy", Match.status == "MUTUAL_INTEREST"),
    )
    return {
        "reciprocity": await reciprocity(session, at - timedelta(days=30)),
        "recommendations": {
            "window_days": 90,
            "total": rec_total,
            "accepted": accepted,
            "accepted_rate": rate(accepted, rec_total),
            "ignored": ignored,
            "ignored_rate": rate(ignored, rec_total),
        },
        "false_matches_reported_30d": false_matches,
        "by_origin": origins,
        "problems": [
            {
                "key": "mutual_sell",
                "label": "Venda × venda registrada como interesse mútuo",
                "count": sell_sell,
                "action": "Correto pela regra",
            },
            {
                "key": "offers_without_category",
                "label": "Produto sem categoria",
                "count": no_category,
                "action": "Reclassificar",
            },
            {
                "key": "mutual_buy_pending",
                "label": "Compra × compra sem oferta compatível",
                "count": buy_buy,
                "action": "Em análise",
            },
            {
                "key": "false_match_reported",
                "label": "Match denunciado como falso",
                "count": false_matches,
                "action": "Ver denúncias",
            },
        ],
    }


# ------------------------------------------------------------------ Suporte e moderação

INCIDENT_ACTIONS = {
    "access.denied": ("Tentativa de abrir dados de outra empresa", "Negado e auditado", "bad"),
    "admin.org.suspend": ("Empresa suspensa pela equipe", "Suspensa", "bad"),
    "admin.org.reactivate": ("Empresa reativada pela equipe", "Concluído", "ok"),
    "org.member_removed": ("Usuário removido da equipe da empresa", "Concluído", "ok"),
    "team.member_removed": ("Usuário removido da equipe da empresa", "Concluído", "ok"),
}


def _report_view(r: Report, cards: dict[uuid.UUID, dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "source": cards.get(r.source_org_id),
        "target": cards.get(r.target_org_id),
        "reason": r.reason,
        "details": r.details,
        "status": r.status,
        "resolution": r.resolution,
        "created_at": iso(r.created_at),
    }


async def _cards(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    if not ids:
        return {}
    rows = (await session.execute(select(Organization).where(Organization.id.in_(ids)))).scalars()
    return {o.id: org_card(o) for o in rows}


async def support(session: AsyncSession) -> dict[str, Any]:
    at = metrics.now()
    reports = (
        (
            await session.execute(
                select(Report).where(Report.status == "open").order_by(Report.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    requests = (
        await session.execute(
            select(AccessRequest, Organization)
            .join(Organization, Organization.id == AccessRequest.org_id)
            .where(AccessRequest.status == "pending")
            .order_by(AccessRequest.created_at)
        )
    ).all()
    reminders = dict(
        (
            await session.execute(
                select(AuditLog.target_id, func.max(AuditLog.created_at))
                .where(AuditLog.action == "admin.access_request.remind")
                .group_by(AuditLog.target_id)
            )
        ).all()
    )
    blocks = (
        (await session.execute(select(OrgBlock).order_by(OrgBlock.created_at.desc()).limit(30)))
        .scalars()
        .all()
    )
    logs = (
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.action.in_(tuple(INCIDENT_ACTIONS)))
                .order_by(AuditLog.created_at.desc())
                .limit(30)
            )
        )
        .scalars()
        .all()
    )
    ids = {r.source_org_id for r in reports} | {r.target_org_id for r in reports}
    ids |= {b.source_org_id for b in blocks} | {b.target_org_id for b in blocks}
    ids |= {lg.org_id for lg in logs if lg.org_id}
    cards = await _cards(session, ids)
    incidents: list[dict[str, Any]] = []
    for b in blocks:
        src, tgt = cards.get(b.source_org_id), cards.get(b.target_org_id)
        incidents.append(
            {
                "at": iso(b.created_at),
                "kind": "block",
                "text": f"{src['name'] if src else '—'} bloqueou {tgt['name'] if tgt else '—'}",
                "status_label": "Bloqueio ativo",
                "severity": "net",
                "orgs": [src, tgt],
            }
        )
    for lg in logs:
        text, label, sev = INCIDENT_ACTIONS[lg.action]
        org = cards.get(lg.org_id) if lg.org_id else None
        incidents.append(
            {
                "at": iso(lg.created_at),
                "kind": lg.action,
                "text": f"{text}: {org['name']}" if org else text,
                "status_label": label,
                "severity": sev,
                "orgs": [org] if org else [],
            }
        )
    incidents.sort(key=lambda i: i["at"] or "", reverse=True)
    return {
        "reports_open": len(reports),
        "reports": [_report_view(r, cards) for r in reports],
        "access_requests": [
            {
                "id": str(req.id),
                "org": org_card(org),
                "cnpj": format_cnpj(org.cnpj),
                "full_name": req.full_name,
                "email": req.email,
                "job_title": req.job_title,
                "created_at": iso(req.created_at),
                "days_waiting": (at - req.created_at).days,
                "last_reminded_at": iso(reminders.get(str(req.id))),
            }
            for req, org in requests
        ],
        "incidents": incidents[:30],
    }


async def review_report(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    status: str,
    resolution: str,
    admin: User,
    ip: str | None,
) -> dict[str, Any]:
    if status not in ("reviewed", "dismissed"):
        raise AppError("Situação inválida.", code="invalid_status")
    report = await session.get(Report, report_id)
    if report is None:
        raise NotFound("Denúncia não encontrada.", code="report_not_found")
    report.status = status
    report.resolution = resolution.strip()
    await audit(
        session,
        admin,
        "admin.report.review",
        org_id=report.target_org_id,
        target_type="report",
        target_id=str(report.id),
        data={"status": status},
        ip=ip,
    )
    await session.flush()
    cards = await _cards(session, {report.source_org_id, report.target_org_id})
    return _report_view(report, cards)


async def remind_access_request(
    session: AsyncSession, req_id: uuid.UUID, *, admin: User, ip: str | None
) -> dict[str, Any]:
    from app.modules.notifications import service as notifications

    req = await session.get(AccessRequest, req_id)
    if req is None:
        raise NotFound("Pedido não encontrado.", code="request_not_found")
    if req.status != "pending":
        raise Conflict("Este pedido já foi respondido.", code="already_decided")
    owners = [u for u in await notifications.members(session, req.org_id) if u.is_org_owner]
    sent = await notifications.notify(
        session,
        req.org_id,
        kind="org.access_request",
        title=f"Lembrete: {req.full_name or req.email} pediu acesso à empresa",
        link="/app/equipe",
        departments=("diretoria",),
        users=owners or None,
        email_vars={"solicitante": req.full_name or req.email, "email_solicitante": req.email},
    )
    await audit(
        session,
        admin,
        "admin.access_request.remind",
        org_id=req.org_id,
        target_type="access_request",
        target_id=str(req.id),
        ip=ip,
    )
    await session.flush()
    return {"ok": True, "notified": sent}


# ------------------------------------------------------------------ team (VIP Network staff)


def role_of(user: User) -> str:
    return user.admin_role or ("owner" if user.is_superuser else "admin")


def team_view(user: User) -> dict[str, Any]:
    role = role_of(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "admin_role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "status": user.status,
        "last_login_at": iso(user.last_login_at),
        "created_at": iso(user.created_at),
    }


async def team(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(User).where(User.kind == "admin").order_by(User.full_name, User.email)
            )
        )
        .scalars()
        .all()
    )
    return [team_view(u) for u in rows]


async def invite_staff(
    session: AsyncSession, *, email: str, full_name: str, admin_role: str, by: User
) -> dict[str, Any]:
    if admin_role not in ADMIN_ROLES:
        raise AppError("Papel inválido.", code="invalid_role")
    if admin_role == "owner" and role_of(by) != "owner":
        raise Forbidden("Só um proprietário pode adicionar outro proprietário.", code="owner_only")
    user = await auth.create_user(
        session,
        email=email,
        password=None,
        kind="admin",
        admin_role=admin_role,
        full_name=full_name,
        status="pending",
    )
    token = await auth.issue_link(session, user, "activate")
    await mail.trigger(
        session,
        "team.invite",
        user=user,
        variables={
            "empresa": "VIP Network",
            "quem_convidou": by.full_name or "Equipe VIP Network",
            "departamento": f"Painel da equipe ({ROLE_LABELS[admin_role]})",
        },
        link=f"/ativar/{token}",
    )
    await audit(
        session,
        by,
        "admin.team.invite",
        target_type="user",
        target_id=str(user.id),
        data={"role": admin_role},
    )
    return team_view(user)


async def update_staff(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    admin_role: str | None,
    blocked: bool | None,
    by: User,
) -> dict[str, Any]:
    user = await session.get(User, user_id)
    if user is None or user.kind != "admin":
        raise NotFound("Pessoa da equipe não encontrada.", code="staff_not_found")
    by_owner = role_of(by) == "owner"
    if (role_of(user) == "owner" or admin_role == "owner") and not by_owner:
        raise Forbidden("Só um proprietário gerencia proprietários.", code="owner_only")
    if admin_role is not None and admin_role not in ADMIN_ROLES:
        raise AppError("Papel inválido.", code="invalid_role")
    if user.id == by.id and (blocked or (admin_role and admin_role != role_of(by))):
        raise AppError("Você não pode bloquear nem mudar o próprio papel.", code="self_change")
    losing_owner = role_of(user) == "owner" and (
        blocked or (admin_role is not None and admin_role != "owner")
    )
    if losing_owner:
        owners = [
            u
            for u in (
                await session.execute(
                    select(User).where(User.kind == "admin", User.status == "active")
                )
            ).scalars()
            if role_of(u) == "owner" and u.id != user.id
        ]
        if not owners:
            raise Conflict("A equipe precisa de pelo menos um proprietário.", code="last_owner")
    if admin_role is not None:
        user.admin_role = admin_role
    if blocked is True and user.status != "blocked":
        user.status = "blocked"
        await auth.revoke_all(session, user.id)
    elif blocked is False and user.status == "blocked":
        user.status = "active" if user.password_hash else "pending"
    await audit(
        session,
        by,
        "admin.team.update",
        target_type="user",
        target_id=str(user.id),
        data={"role": admin_role, "blocked": blocked},
    )
    await session.flush()
    return team_view(user)

"""Recommendation cards and market reports (scope §10, §18).

Reports are queued as an ``AIJob`` of the MarketIntelligenceAgent (``weos.jobs``). Without a
WeOS token the job runs :func:`build_local_report`: built only from the org's own profile and
catalog, the protected aggregate statistics of the network and published (public) data of
other companies. Every section carries a confidence; nothing unverified is stated as fact.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.auth.deps import Ctx
from app.modules.auth.models import User
from app.modules.billing.service import brl
from app.modules.catalog.models import Offer, PurchaseNeed
from app.modules.intelligence import engine
from app.modules.intelligence.models import MarketReport, Recommendation
from app.modules.organizations.models import Organization
from app.modules.organizations.views import iso, org_card

REPORT_AGENT = "MarketIntelligenceAgent"
PROMPT_VERSION = "mi-2026.11"

SECTIONS: tuple[tuple[str, str], ...] = (
    ("resumo", "Resumo executivo"),
    ("posicionamento", "Posicionamento"),
    ("mercado", "Mercado de atuação"),
    ("oportunidades", "Oportunidades comerciais"),
    ("clientes", "Potenciais clientes"),
    ("fornecedores", "Alternativas de fornecedores"),
    ("custos", "Redução de custos"),
    ("tendencias", "Tendências e riscos"),
    ("recomendacoes", "Recomendações estratégicas"),
    ("proximas_acoes", "Próximas ações"),
)
CONFIDENCE = ("alta", "média", "baixa")

REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["sections"],
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["key", "title", "confidence"],
                "properties": {
                    "key": {"type": "string", "enum": [k for k, _ in SECTIONS]},
                    "title": {"type": "string"},
                    "confidence": {"type": "string", "enum": list(CONFIDENCE)},
                    "body": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "url": {"type": "string"},
                    "date": {"type": "string"},
                },
            },
        },
    },
}

# which department area sees each card kind (economy/supplier use the org's private purchases)
KIND_AREA = {
    "economy": "purchases",
    "supplier": "purchases",
    "buyer": "sales",
    "partner": "network",
    "solution": "purchases",
    "event": "events",
}


def visible_kinds(ctx: Ctx) -> list[str]:
    return [k for k, a in KIND_AREA.items() if ctx.can(a)]


def rec_view(rec: Recommendation, target: Organization | None) -> dict[str, Any]:
    return {
        "id": str(rec.id),
        "kind": rec.kind,
        "title": rec.title,
        "body": rec.body,
        "score": rec.score,
        "status": rec.status,
        "estimate": rec.kind == "economy",
        "data": rec.data,
        "org": org_card(target) if target else None,
        "created_at": iso(rec.created_at),
    }


async def list_recommendations(
    session: AsyncSession, ctx: Ctx, *, limit: int = 50
) -> list[dict[str, Any]]:
    kinds = visible_kinds(ctx)
    if not kinds:
        return []
    blocked = await engine.blocked_ids(session, ctx.org_id)
    rows = (
        await session.execute(
            select(Recommendation, Organization)
            .outerjoin(Organization, Organization.id == Recommendation.target_org_id)
            .where(
                Recommendation.org_id == ctx.org_id,
                Recommendation.status == "new",
                Recommendation.kind.in_(kinds),
            )
            .order_by(Recommendation.score.desc().nulls_last(), Recommendation.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [rec_view(r, o) for r, o in rows if r.target_org_id not in blocked]


async def dismiss(session: AsyncSession, ctx: Ctx, rec_id: uuid.UUID) -> None:
    rec = await session.get(Recommendation, rec_id)
    if rec is None or rec.org_id != ctx.org_id:
        raise NotFound("Recomendação não encontrada.", code="recommendation_not_found")
    rec.status = "dismissed"
    await session.flush()


async def potential_economy_cents(session: AsyncSession, org_id: uuid.UUID) -> int:
    blocked = await engine.blocked_ids(session, org_id)
    rows = (
        await session.execute(
            select(Recommendation).where(
                Recommendation.org_id == org_id,
                Recommendation.kind == "economy",
                Recommendation.status == "new",
            )
        )
    ).scalars()
    return sum(
        int((r.data or {}).get("net_cents") or 0) for r in rows if r.target_org_id not in blocked
    )


# ------------------------------------------------------------------ reports


def report_view(rep: MarketReport, *, full: bool = True) -> dict[str, Any]:
    out = {
        "id": str(rep.id),
        "status": rep.status,
        "created_at": iso(rep.created_at),
        "finished_at": iso(rep.finished_at),
        "error": rep.error if rep.status == "failed" else "",
    }
    if full:
        out["sections"] = (rep.content or {}).get("sections", [])
        out["sources"] = (rep.content or {}).get("sources", [])
        out["based_on"] = (rep.content or {}).get("based_on", "")
    return out


async def create_report(session: AsyncSession, ctx: Ctx) -> MarketReport:
    """One report in progress per company: asking again returns the one already queued."""
    from app.modules.weos import jobs

    current = (
        await session.execute(
            select(MarketReport)
            .where(
                MarketReport.org_id == ctx.org_id, MarketReport.status.in_(("queued", "running"))
            )
            .order_by(MarketReport.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if current is not None:
        return current
    rep = MarketReport(org_id=ctx.org_id, requested_by=ctx.user_id, status="queued")
    session.add(rep)
    await session.flush()
    await jobs.enqueue(
        session,
        REPORT_AGENT,
        ctx.org_id,
        {"report_id": str(rep.id)},
        f"report:{ctx.org_id}",
        user_id=ctx.user_id,
    )
    return rep


async def list_reports(session: AsyncSession, org_id: uuid.UUID) -> list[MarketReport]:
    return list(
        (
            await session.execute(
                select(MarketReport)
                .where(MarketReport.org_id == org_id)
                .order_by(MarketReport.created_at.desc())
                .limit(30)
            )
        ).scalars()
    )


async def get_report(session: AsyncSession, org_id: uuid.UUID, rep_id: uuid.UUID) -> MarketReport:
    rep = await session.get(MarketReport, rep_id)
    if rep is None or rep.org_id != org_id:
        raise NotFound("Relatório não encontrado.", code="report_not_found")
    return rep


def _sec(key: str, confidence: str, body: str = "", items: list[str] | None = None) -> dict:
    return {
        "key": key,
        "title": dict(SECTIONS)[key],
        "confidence": confidence,
        "body": body,
        "items": items or [],
    }


async def report_context(session: AsyncSession, org: Organization) -> dict[str, Any]:
    """What a report may use: own profile and catalog, aggregate network counts, published
    data of other companies. Never another company's private purchases or mentorship data."""
    blocked = await engine.blocked_ids(session, org.id)
    offers = list(
        (
            await session.execute(
                select(Offer).where(Offer.org_id == org.id, Offer.status == "published")
            )
        ).scalars()
    )
    needs = list(
        (
            await session.execute(
                select(PurchaseNeed).where(
                    PurchaseNeed.org_id == org.id, PurchaseNeed.active.is_(True)
                )
            )
        ).scalars()
    )
    active_orgs = (
        await session.execute(
            select(func.count()).select_from(Organization).where(Organization.status == "active")
        )
    ).scalar_one()
    same_sector = (
        await session.execute(
            select(func.count())
            .select_from(Organization)
            .where(
                Organization.status == "active",
                Organization.sector == org.sector,
                Organization.id != org.id,
            )
        )
    ).scalar_one()
    categories = {engine._norm(o.category) for o in offers if o.category}
    pub_needs = [
        n
        for n in (
            await session.execute(
                select(PurchaseNeed).where(
                    PurchaseNeed.visibility == "published",
                    PurchaseNeed.active.is_(True),
                    PurchaseNeed.org_id != org.id,
                )
            )
        ).scalars()
        if n.org_id not in blocked
        and any(engine.same_item(o.category, o.name, n.category, n.name) for o in offers)
    ]
    return {
        "org": org,
        "offers": offers,
        "needs": needs,
        "active_orgs": int(active_orgs),
        "same_sector": int(same_sector),
        "categories": sorted(categories),
        "published_needs": pub_needs,
    }


async def build_local_report(session: AsyncSession, org: Organization) -> dict[str, Any]:
    """Local report generator (MarketIntelligenceAgent fallback). Refreshes the cards first so
    the report and the Visão Geral agree."""
    await engine.refresh_for(session, org.id)
    ctx = await report_context(session, org)
    recs = list(
        (
            await session.execute(
                select(Recommendation, Organization)
                .outerjoin(Organization, Organization.id == Recommendation.target_org_id)
                .where(Recommendation.org_id == org.id, Recommendation.status == "new")
                .order_by(Recommendation.score.desc().nulls_last())
            )
        ).all()
    )
    by_kind: dict[str, list[tuple[Recommendation, Organization | None]]] = {}
    for r, o in recs:
        by_kind.setdefault(r.kind, []).append((r, o))
    economy = by_kind.get("economy", [])
    economy_total = sum(int(r.data.get("net_cents") or 0) for r, _ in economy)
    sector = engine.SECTOR_LABEL.get(org.sector, org.sector)
    place = f"{org.city}/{org.state}" if org.city else (org.state or "local não informado")
    offers, needs = ctx["offers"], ctx["needs"]
    today = datetime.now(UTC).date().isoformat()

    resumo = (
        f"{org.display_name} atua em {sector.lower()}"
        + (f" ({org.segment})" if org.segment else "")
        + f", com sede em {place}. Tem {len(offers)} item(ns) publicado(s) para venda e "
        f"{len(needs)} item(ns) de compra cadastrado(s)."
    )
    if economy_total:
        resumo += (
            f" A rede já mostra fornecedores com potencial de economia estimada de "
            f"{brl(economy_total)} por mês."
        )
    if by_kind.get("buyer"):
        resumo += f" {len(by_kind['buyer'])} empresa(s) publicaram demanda do que você vende."

    cat_counts = Counter(o.category for o in offers if o.category)
    sections = [
        _sec("resumo", "alta", resumo),
        _sec(
            "posicionamento",
            "média" if offers else "baixa",
            "Baseado no perfil e no catálogo publicados pela própria empresa.",
            [f"{c}: {n} item(ns)" for c, n in cat_counts.most_common(5)]
            or [
                "Catálogo de vendas ainda vazio: publique produtos e serviços para melhorar a análise."
            ],
        ),
        _sec(
            "mercado",
            "alta",
            f"A rede VIP Network tem {ctx['active_orgs']} empresas ativas; "
            f"{ctx['same_sector']} delas no setor {sector.lower()}.",
        ),
        _sec(
            "oportunidades",
            "alta" if by_kind.get("buyer") or by_kind.get("partner") else "média",
            "Cards também disponíveis na Visão Geral.",
            [r.title for r, _ in (by_kind.get("buyer", []) + by_kind.get("partner", []))[:5]]
            or ["Nenhuma oportunidade nova encontrada na rede neste momento."],
        ),
        _sec(
            "clientes",
            "alta" if ctx["published_needs"] else "baixa",
            "Empresas que publicaram demanda compatível com o que você vende.",
            sorted({o.display_name for r, o in by_kind.get("buyer", []) if o})[:8]
            or ["Ainda não há demandas publicadas compatíveis com o seu catálogo."],
        ),
        _sec(
            "fornecedores",
            "alta" if by_kind.get("supplier") or economy else "baixa",
            "Fornecedores da rede com ofertas publicadas dos itens que você compra.",
            sorted({o.display_name for r, o in by_kind.get("supplier", []) + economy if o})[:8]
            or ["Cadastre o que sua empresa compra para receber alternativas de fornecedores."],
        ),
        _sec(
            "custos",
            "média" if economy else "baixa",
            (
                f"Economia potencial estimada: {brl(economy_total)} por mês. Valores são "
                "estimativas (já descontam frete e ajustes estimados) até a confirmação da "
                "proposta e da equivalência técnica."
                if economy
                else "Sem comparação de preço disponível: informe o preço pago e o volume "
                "mensal nos itens de compra (ficam privados)."
            ),
            [r.title for r, _ in economy[:5]],
        ),
        _sec(
            "tendencias",
            "baixa",
            "Nenhuma fonte externa verificada foi usada nesta versão do relatório. Os pontos "
            "abaixo são hipóteses gerais para investigar, não fatos confirmados.",
            [
                "Verificar a variação de preço dos principais insumos do setor nos últimos meses.",
                "Avaliar concentração de clientes e fornecedores (dependência de poucos nomes).",
            ],
        ),
        _sec(
            "recomendacoes",
            "média",
            "",
            [
                *(
                    ["Negociar com os fornecedores de menor preço indicados em Redução de custos."]
                    if economy
                    else []
                ),
                *(
                    ["Responder às empresas que publicaram demanda do que você vende."]
                    if by_kind.get("buyer")
                    else []
                ),
                "Manter o catálogo de vendas e o de compras atualizados para melhorar os matches.",
            ],
        ),
        _sec(
            "proximas_acoes",
            "alta",
            "",
            [r.title for r, _ in recs[:3]] or ["Completar o catálogo e o perfil da empresa."],
        ),
    ]
    return {
        "sections": sections,
        "sources": [
            {"name": "Perfil e catálogo da empresa", "date": today},
            {"name": "Estatísticas agregadas da rede VIP Network", "date": today},
            {"name": "Demandas e ofertas publicadas na rede", "date": today},
        ],
        "based_on": "seu perfil, catálogo e estatísticas agregadas da rede",
        "generated": "local",
    }


def remote_report_payload(ctx: dict[str, Any]) -> dict[str, Any]:
    """Data sent to WeOS for the report: own data + aggregate counts + public demand names."""
    org: Organization = ctx["org"]
    return {
        "company": {
            "name": org.display_name,
            "sector": org.sector,
            "segment": org.segment,
            "city": org.city,
            "state": org.state,
            "website": org.website,
            # free text written by the company / fetched from its site: data only
            "description": org.description[:3000],
        },
        "offers": [
            {"name": o.name, "category": o.category, "specs": o.specs[:500]}
            for o in ctx["offers"][:50]
        ],
        "needs": [{"name": n.name, "category": n.category} for n in ctx["needs"][:50]],
        "network": {
            "active_companies": ctx["active_orgs"],
            "same_sector": ctx["same_sector"],
            "published_demands_matching_offers": len(ctx["published_needs"]),
        },
    }


def normalize_remote_report(data: dict[str, Any]) -> dict[str, Any]:
    """Keep only known sections/fields from the agent answer (schema already validated)."""
    known = dict(SECTIONS)
    sections = []
    for s in data.get("sections", []):
        if s["key"] not in known:
            continue
        sections.append(
            _sec(
                s["key"],
                s["confidence"],
                str(s.get("body") or "")[:4000],
                [str(i)[:500] for i in (s.get("items") or [])][:12],
            )
        )
    today = datetime.now(UTC).date().isoformat()
    sources = [
        {
            "name": str(x.get("name"))[:200],
            "url": str(x.get("url") or "")[:400],
            "date": str(x.get("date") or "")[:20],
        }
        for x in data.get("sources", [])[:20]
    ]
    sources.append({"name": "Estatísticas agregadas da rede VIP Network", "date": today})
    return {
        "sections": sections,
        "sources": sources,
        "based_on": "seu perfil, catálogo, site e estatísticas agregadas da rede",
        "generated": "weos",
    }


async def finish_report(
    session: AsyncSession, rep: MarketReport, content: dict[str, Any] | None, error: str = ""
) -> None:
    from app.modules.notifications import service as notifications

    rep.finished_at = datetime.now(UTC)
    if content is None:
        rep.status = "failed"
        rep.error = error or "Não foi possível gerar o relatório agora. Tente de novo mais tarde."
        return
    rep.status = "ready"
    rep.content = content
    rep.error = ""
    user = await session.get(User, rep.requested_by) if rep.requested_by else None
    await notifications.notify(
        session,
        rep.org_id,
        kind="report.ready",
        title="Seu relatório de mercado está pronto",
        link=f"/app/inteligencia?relatorio={rep.id}",
        users=[user] if user is not None else None,
        departments=("diretoria",),
    )

"""Team panel › Agentes WeOS: jobs, failures, latency and consumption per agent (scope §19.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.modules.auth.deps import AdminUser, DbSession
from app.modules.weos import client, jobs
from app.modules.weos.models import AGENTS, AIJob

admin_router = APIRouter(prefix="/admin/agents", tags=["admin"])

FUNCTIONS = {
    "CompanyProfileAgent": "Descrição e categoria da empresa",
    "ProductClassificationAgent": "Normaliza produtos e categorias",
    "MatchmakingAgent": "Compatibilidade e explicação",
    "ProcurementAgent": "Fornecedores e economia",
    "SalesOpportunityAgent": "Oportunidades de venda",
    "MarketIntelligenceAgent": "Relatórios de mercado",
    "NetworkingAgent": "Conexões e mesas de eventos",
    "MentorshipAgent": "Apoio a mentorados",
}


class RetryIn(BaseModel):
    agent: str | None = None


@admin_router.get("")
async def agents_overview(session: DbSession, _: AdminUser) -> dict[str, Any]:
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recent = AIJob.created_at >= day_ago
    rows = (
        await session.execute(
            select(
                AIJob.agent,
                func.count().filter(recent),
                func.count().filter(recent, AIJob.status == "done"),
                func.count().filter(recent, AIJob.error != ""),
                func.count().filter(AIJob.status == "dead"),
                func.count().filter(AIJob.status.in_(("queued", "running"))),
                func.percentile_cont(0.95)
                .within_group(AIJob.latency_ms)
                .filter(recent, AIJob.status == "done"),
                func.coalesce(
                    func.sum(case((AIJob.created_at >= month_start, AIJob.cost_cents), else_=0)),
                    0,
                ),
            ).group_by(AIJob.agent)
        )
    ).all()
    stats = {r[0]: r for r in rows}
    p95_all = (
        await session.execute(
            select(
                func.percentile_cont(0.95)
                .within_group(AIJob.latency_ms)
                .filter(recent, AIJob.status == "done")
            )
        )
    ).scalar_one()
    agents = []
    for name in AGENTS:
        r = stats.get(name)
        jobs_24h, done, failures, dead, pending, p95, cost = (
            (r[1], r[2], r[3], r[4], r[5], r[6], r[7]) if r else (0, 0, 0, 0, 0, None, 0)
        )
        agents.append(
            {
                "agent": name,
                "function": FUNCTIONS.get(name, ""),
                "jobs_24h": jobs_24h,
                "done_24h": done,
                "failures_24h": failures,
                "dead": dead,
                "pending": pending,
                "p95_ms": int(p95) if p95 is not None else None,
                "cost_month_cents": int(cost or 0),
                "status": "with_failures" if dead else "normal",
                "status_label": "Com falhas" if dead else "Normal",
            }
        )
    total = sum(a["jobs_24h"] for a in agents)
    done_total = sum(a["done_24h"] for a in agents)
    return {
        "weos_configured": client.configured(),
        "max_attempts": jobs.MAX_ATTEMPTS,
        "totals": {
            "jobs_24h": total,
            "done_pct": round(done_total * 100 / total, 1) if total else None,
            "failures_24h": sum(a["failures_24h"] for a in agents),
            "dead": sum(a["dead"] for a in agents),
            "p95_ms": int(p95_all) if p95_all is not None else None,
            "cost_month_cents": sum(a["cost_month_cents"] for a in agents),
        },
        "agents": agents,
    }


@admin_router.post("/retry-dead")
async def retry_dead(
    session: DbSession, _: AdminUser, body: RetryIn | None = None
) -> dict[str, int]:
    return {"requeued": await jobs.retry_dead(session, body.agent if body else None)}

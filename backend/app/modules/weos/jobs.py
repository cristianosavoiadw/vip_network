"""AI job queue (scope §19.1): no duplicate execution, retry with exponential backoff,
dead-letter after ``MAX_ATTEMPTS``, latency / prompt version / model / cost recorded.

With ``VIP_WEOS_API_TOKEN`` the job is sent to the WeOS agent (``client.run_task``); without
it, the LOCAL fallback of the agent runs:

- MarketIntelligenceAgent → ``intelligence.service.build_local_report``;
- CompanyProfileAgent → ``organizations.service`` description suggestion (waits for approval);
- MatchmakingAgent / ProcurementAgent / SalesOpportunityAgent → ``intelligence.engine.refresh_for``.

Agents without a local handler finish as ``done`` with ``result.skipped``.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.weos import client
from app.modules.weos.models import AGENTS, AIJob

log = logging.getLogger("vip.weos.jobs")
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 30  # 30 s, 60 s, ... between attempts
TICK_SECONDS = 5
BATCH = 10
LOCAL_MODEL = "local-rules"
LOCAL_PROMPT = "local-1"

Handler = Callable[[AsyncSession, AIJob], Awaitable[dict[str, Any]]]


class JobError(Exception):
    """Permanent failure: no retry (bad input, missing row)."""


async def enqueue(
    session: AsyncSession,
    agent: str,
    org_id: uuid.UUID | None,
    input: dict[str, Any],  # noqa: A002 - name of the column
    dedupe_key: str | None,
    *,
    user_id: uuid.UUID | None = None,
) -> AIJob:
    """Queue a job. While a job with the same ``dedupe_key`` is queued or running, that job is
    returned instead of a new one."""
    if agent not in AGENTS:
        raise ValueError(f"unknown agent {agent}")
    if dedupe_key:
        existing = (
            await session.execute(
                select(AIJob)
                .where(AIJob.dedupe_key == dedupe_key, AIJob.status.in_(("queued", "running")))
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    job = AIJob(
        org_id=org_id,
        user_id=user_id,
        agent=agent,
        dedupe_key=dedupe_key,
        status="queued",
        input=input,
    )
    session.add(job)
    await session.flush()
    return job


def _meta(job: AIJob) -> dict[str, Any]:
    return {
        "tenant": str(job.org_id) if job.org_id else "",
        "user": str(job.user_id) if job.user_id else "",
        "job_id": str(job.id),
    }


# ------------------------------------------------------------------ handlers


async def _market_report(session: AsyncSession, job: AIJob) -> dict[str, Any]:
    from app.modules.intelligence import service as intel
    from app.modules.intelligence.models import MarketReport
    from app.modules.organizations.models import Organization

    rep = await session.get(MarketReport, uuid.UUID(str(job.input.get("report_id"))))
    if rep is None:
        raise JobError("Relatório não existe mais.")
    org = await session.get(Organization, rep.org_id)
    if org is None:
        raise JobError("Empresa não existe mais.")
    rep.status = "running"
    if client.configured():
        await intel.engine.refresh_for(session, org.id)
        ctx = await intel.report_context(session, org)
        res = await client.run_task(
            job.agent,
            task=(
                "Produza um relatório de mercado para a empresa em `data.company`, com as seções "
                + ", ".join(t for _, t in intel.SECTIONS)
                + ". Cada seção com grau de confiança (alta, média ou baixa). Liste fontes com "
                "data. Não apresente informação não verificada como fato."
            ),
            data=intel.remote_report_payload(ctx),
            schema=intel.REPORT_SCHEMA,
            metadata=_meta(job),
            prompt_version=intel.PROMPT_VERSION,
        )
        _record(job, res.model, intel.PROMPT_VERSION, res.cost_cents)
        content = intel.normalize_remote_report(res.data)
    else:
        content = await intel.build_local_report(session, org)
        _record(job, LOCAL_MODEL, LOCAL_PROMPT, 0)
    await intel.finish_report(session, rep, content)
    return {"report_id": str(rep.id), "sections": len(content["sections"])}


PROFILE_SCHEMA = {
    "type": "object",
    "required": ["description"],
    "properties": {"description": {"type": "string"}, "sector": {"type": "string"}},
}


async def _company_profile(session: AsyncSession, job: AIJob) -> dict[str, Any]:
    from app.modules.catalog.models import Offer
    from app.modules.organizations import service as orgs
    from app.modules.organizations.models import AiSuggestion, Organization

    org = await session.get(Organization, job.org_id) if job.org_id else None
    if org is None:
        raise JobError("Empresa não existe mais.")
    if not client.configured():
        sug = await orgs.create_description_suggestion(session, org)
        _record(job, LOCAL_MODEL, LOCAL_PROMPT, 0)
        return {"suggestion_id": str(sug.id)}
    offers = [
        o.name
        for o in (
            await session.execute(
                select(Offer).where(Offer.org_id == org.id, Offer.status == "published")
            )
        ).scalars()
    ]
    res = await client.run_task(
        job.agent,
        task="Sugira uma descrição empresarial objetiva (até 600 caracteres, pt-BR) e o setor.",
        data={
            "official": org.official,
            "website": org.website,
            "description": org.description[:3000],
            "offers": offers[:30],
        },
        schema=PROFILE_SCHEMA,
        metadata=_meta(job),
        prompt_version="cp-2026.11",
    )
    _record(job, res.model, "cp-2026.11", res.cost_cents)
    await session.execute(
        AiSuggestion.__table__.update()
        .where(
            AiSuggestion.org_id == org.id,
            AiSuggestion.field == "description",
            AiSuggestion.status == "pending",
        )
        .values(status="rejected")
    )
    sug = AiSuggestion(
        org_id=org.id,
        field="description",
        value=str(res.data["description"])[:2000],
        source="weos",
    )
    session.add(sug)
    await session.flush()
    return {"suggestion_id": str(sug.id)}


RANK_SCHEMA = {
    "type": "object",
    "required": ["ranking"],
    "properties": {
        "ranking": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "integer"},
                    "explanation": {"type": "string"},
                },
            },
        }
    },
}


async def _matching(session: AsyncSession, job: AIJob) -> dict[str, Any]:
    """The numbers (savings, candidates) always come from the local engine; WeOS, when
    configured, only re-ranks and explains the cards it was given."""
    from app.modules.intelligence import engine

    if job.org_id is None:
        raise JobError("Job sem empresa.")
    recs = await engine.refresh_for(session, job.org_id)
    if not client.configured() or not recs:
        _record(job, LOCAL_MODEL, LOCAL_PROMPT, 0)
        return {"recommendations": len(recs)}
    by_id = {str(r.id): r for r in recs}
    res = await client.run_task(
        job.agent,
        task="Ordene os cards por potencial de negócio e explique cada um em uma frase, sem "
        "inventar números.",
        data={
            "cards": [
                {"id": str(r.id), "kind": r.kind, "title": r.title, "body": r.body}
                for r in recs
                if r.kind != "economy"  # private purchase data stays local
            ]
        },
        schema=RANK_SCHEMA,
        metadata=_meta(job),
        prompt_version="mm-2026.11",
    )
    _record(job, res.model, "mm-2026.11", res.cost_cents)
    for item in res.data["ranking"]:
        rec = by_id.get(item["id"])
        if rec is None or rec.kind == "economy":
            continue
        if isinstance(item.get("score"), int):
            rec.score = max(0, min(99, item["score"]))
        if item.get("explanation"):
            rec.body = str(item["explanation"])[:600]
        rec.origin = "weos"
    return {"recommendations": len(recs)}


HANDLERS: dict[str, Handler] = {
    "MarketIntelligenceAgent": _market_report,
    "CompanyProfileAgent": _company_profile,
    "MatchmakingAgent": _matching,
    "ProcurementAgent": _matching,
    "SalesOpportunityAgent": _matching,
}


def _record(job: AIJob, model: str, prompt_version: str, cost_cents: int | None) -> None:
    job.model = model[:60]
    job.prompt_version = prompt_version[:20]
    job.cost_cents = cost_cents


# ------------------------------------------------------------------ runner


async def _on_dead(session: AsyncSession, job: AIJob) -> None:
    if job.agent == "MarketIntelligenceAgent" and job.input.get("report_id"):
        from app.modules.intelligence import service as intel
        from app.modules.intelligence.models import MarketReport

        rep = await session.get(MarketReport, uuid.UUID(str(job.input["report_id"])))
        if rep is not None and rep.status in ("queued", "running"):
            await intel.finish_report(session, rep, None)


async def run_job(session: AsyncSession, job: AIJob) -> AIJob:
    """Run one attempt of ``job`` in ``session`` (the caller commits)."""
    now = datetime.now(UTC)
    job.status = "running"
    job.attempts += 1
    job.started_at = now
    await session.flush()
    handler = HANDLERS.get(job.agent)
    started = time.monotonic()
    try:
        if handler is None:
            result: dict[str, Any] = {"skipped": "sem processamento local para este agente"}
        else:
            async with session.begin_nested():
                result = await handler(session, job)
    except JobError as exc:
        await session.refresh(job)  # the savepoint rollback expired it
        job.status = "failed"
        job.error = str(exc)[:1000]
        job.finished_at = datetime.now(UTC)
        await _on_dead(session, job)
        return job
    except Exception as exc:  # noqa: BLE001 - retried, then dead-letter
        await session.refresh(job)
        job.error = f"{exc.__class__.__name__}: {exc}"[:1000]
        job.latency_ms = int((time.monotonic() - started) * 1000)
        if job.attempts >= MAX_ATTEMPTS:
            job.status = "dead"
            job.finished_at = datetime.now(UTC)
            job.next_attempt_at = None
            await _on_dead(session, job)
            log.warning("ai job %s (%s) dead: %s", job.id, job.agent, job.error)
        else:
            job.status = "queued"
            job.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=BACKOFF_SECONDS * 2 ** (job.attempts - 1)
            )
        return job
    job.status = "done"
    job.result = result
    job.latency_ms = int((time.monotonic() - started) * 1000)
    job.finished_at = datetime.now(UTC)
    job.next_attempt_at = None
    return job


async def due_ids(session: AsyncSession, *, limit: int = BATCH) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    rows = await session.execute(
        select(AIJob.id)
        .where(
            AIJob.status == "queued",
            or_(AIJob.next_attempt_at.is_(None), AIJob.next_attempt_at <= now),
        )
        .order_by(AIJob.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return [r[0] for r in rows]


async def tick() -> int:
    """Process the due jobs, each in its own transaction. Returns how many ran."""
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        ids = await due_ids(session)
        if not ids:
            return 0
        # claim them: running jobs are skipped by other workers
        for job_id in ids:
            job = await session.get(AIJob, job_id)
            if job is not None:
                job.status = "running"
        await session.commit()
    for job_id in ids:
        async with SessionLocal() as session:
            job = await session.get(AIJob, job_id)
            if job is None:
                continue
            try:
                await run_job(session, job)
                await session.commit()
            except Exception:  # noqa: BLE001 - keep the batch going
                log.exception("ai job %s crashed", job_id)
                await session.rollback()
    return len(ids)


async def recover_stale(session: AsyncSession, *, minutes: int = 15) -> None:
    """Jobs left ``running`` by a crash go back to the queue (their attempt counts)."""
    cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
    for job in (
        await session.execute(
            select(AIJob).where(
                AIJob.status == "running",
                or_(AIJob.started_at.is_(None), AIJob.started_at < cutoff),
                AIJob.updated_at < cutoff,
            )
        )
    ).scalars():
        job.status = "dead" if job.attempts >= MAX_ATTEMPTS else "queued"
        job.error = job.error or "Execução interrompida."


async def retry_dead(session: AsyncSession, agent: str | None = None) -> int:
    from app.modules.intelligence.models import MarketReport

    q = select(AIJob).where(AIJob.status == "dead")
    if agent:
        q = q.where(AIJob.agent == agent)
    n = 0
    for job in (await session.execute(q)).scalars():
        job.status = "queued"
        job.attempts = 0
        job.next_attempt_at = None
        job.error = ""
        job.finished_at = None
        if job.input.get("report_id"):
            rep = await session.get(MarketReport, uuid.UUID(str(job.input["report_id"])))
            if rep is not None and rep.status == "failed":
                rep.status = "queued"
                rep.error = ""
                rep.finished_at = None
        n += 1
    await session.flush()
    return n


async def tick_forever() -> None:
    from app.db.session import SessionLocal

    last_recover = 0.0
    while True:
        try:
            if time.monotonic() - last_recover > 300:
                async with SessionLocal() as session:
                    await recover_stale(session)
                    await session.commit()
                last_recover = time.monotonic()
            ran = await tick()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("ai jobs tick failed")
            ran = 0
        if not ran:
            await asyncio.sleep(TICK_SECONDS)

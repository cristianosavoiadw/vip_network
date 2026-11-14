"""/admin/analytics: MRR, ARR, churn, LTV, revenue by source, funnel, cohorts, main indicator."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.modules.analytics import service
from app.modules.auth.deps import AdminUser, DbSession

router = APIRouter(prefix="/admin/analytics", tags=["admin"])


@router.get("")
async def analytics(admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await service.analytics(session)

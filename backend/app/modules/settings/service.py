"""Platform settings with defaults. Keys:

- ``access``: entry mode and invite rules (Admin › Acesso e convites).
- ``mail``: sending caps and grouping (Admin › E-mails › Configuração).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.settings.models import PlatformSetting

ACCESS_MODES = ("invite", "paid", "both")

DEFAULTS: dict[str, dict[str, Any]] = {
    "access": {
        # invite = closed club · paid = anyone subscribes, invites off · both
        "mode": "both",
        # VIP plan validity in months; fixed at 12 in the "invite" mode
        "vip_months": 12,
        "invites_per_member": 3,
        # invitees | all (subscribers too)
        "who_invites": "invitees",
        "invite_ttl_days": 30,
        # the invite is used only by someone signing up with the invited e-mail
        "bind_email": True,
        "return_expired": True,
        "vip_reminders": True,
    },
    "mail": {
        "hourly_cap": 0,  # 0 = environment default
        "daily_cap": 0,
        "group_activity": True,
        "warmup_day": 0,
    },
}


async def get(session: AsyncSession, key: str) -> dict[str, Any]:
    row = await session.get(PlatformSetting, key)
    return {**DEFAULTS.get(key, {}), **(row.value if row else {})}


async def put(
    session: AsyncSession, key: str, value: dict[str, Any], *, user_id: uuid.UUID | None
) -> dict[str, Any]:
    if key not in DEFAULTS:
        raise AppError("Configuração desconhecida.", code="unknown_setting")
    merged = {**await get(session, key), **{k: v for k, v in value.items() if k in DEFAULTS[key]}}
    if key == "access":
        merged = validate_access(merged)
    row = await session.get(PlatformSetting, key)
    if row is None:
        session.add(PlatformSetting(key=key, value=merged, updated_by=user_id))
    else:
        row.value = merged
        row.updated_by = user_id
    await session.flush()
    return merged


def validate_access(conf: dict[str, Any]) -> dict[str, Any]:
    if conf["mode"] not in ACCESS_MODES:
        raise AppError("Modo de entrada inválido.", code="invalid_mode")
    if int(conf["vip_months"]) not in (3, 6, 12, 24):
        raise AppError("Validade do Plano VIP: 3, 6, 12 ou 24 meses.", code="invalid_vip_months")
    per = int(conf["invites_per_member"])
    if not 1 <= per <= 20:
        raise AppError("Convites por empresa: de 1 a 20.", code="invalid_invites")
    if int(conf["invite_ttl_days"]) not in (7, 15, 30, 60):
        raise AppError("Validade do link: 7, 15, 30 ou 60 dias.", code="invalid_ttl")
    if conf["who_invites"] not in ("invitees", "all"):
        raise AppError("Opção de quem indica inválida.", code="invalid_who")
    if conf["mode"] == "invite":
        conf["who_invites"] = "invitees"
    return conf


def vip_months(conf: dict[str, Any]) -> int:
    return 12 if conf["mode"] == "invite" else int(conf["vip_months"])

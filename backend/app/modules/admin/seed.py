"""``manage.py seed``: platform defaults (idempotent) and, with ``--demo``, example companies
for local development. Demo data never runs in production (VIP_ENV=prod refuses it)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.mail import service as mail
from app.modules.mentorship.models import Mentor

MENTOR_PHOTO = (
    Path(__file__).resolve().parents[4] / "frontend" / "public" / "img" / "carol.jpeg"
)


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


async def _mentor_photo() -> str:
    """The lead mentor's portrait, uploaded to vip/vip-network/mentor/ (empty if unavailable)."""
    from app.modules.media import service as media

    data = await asyncio.to_thread(_read, MENTOR_PHOTO)
    if data is None:
        return ""
    try:
        return (await media.save_platform_image("mentor", data))["url"]
    except Exception:  # noqa: BLE001 - storage down: no photo
        return ""


async def run(session: AsyncSession, *, demo: bool = False) -> list[str]:
    out: list[str] = []
    n = await mail.seed_templates(session)
    out.append(f"Modelos de e-mail criados: {n}")
    if not (await session.execute(select(Mentor.id))).first():
        session.add(
            Mentor(
                name="Caroline Gonçalves",
                headline="Mentora de negócios e estratégia B2B",
                bio="Orientação estratégica para vender mais, comprar melhor e criar parcerias de alto valor.",
                photo_url=await _mentor_photo(),
                is_lead=True,
            )
        )
        out.append("Mentora principal criada: Caroline Gonçalves")
    else:  # older installs pointed at a site file: move the photo into the bucket
        for mentor in (await session.execute(select(Mentor))).scalars():
            if mentor.is_lead and (not mentor.photo_url or mentor.photo_url.startswith("/img/")):
                mentor.photo_url = await _mentor_photo() or mentor.photo_url
    if demo:
        if get_settings().env == "prod":
            out.append("Dados de exemplo recusados em produção.")
            return out
        try:
            from app.modules.admin import demo as demo_data
        except ModuleNotFoundError:
            out.append("Dados de exemplo ainda não disponíveis.")
            return out
        out.extend(await demo_data.run(session))
    return out

"""/media: upload of company images (logo, cover, offer photos), upload of platform images by
the team (events, mentors) and the route that serves every image from the bucket.

Images are profile content shown inside the network and in e-mails, so serving them needs no
login; keys are random, so they cannot be listed or guessed.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.core import storage
from app.core.errors import NotFound
from app.modules.auth.deps import AdminUser, Ctx, area_any_status
from app.modules.media import service

public_router = APIRouter(prefix="/media", tags=["media"])
router = APIRouter(prefix="/media", tags=["media"])
admin_router = APIRouter(prefix="/admin/media", tags=["admin"])

CompanyCtx = Annotated[Ctx, Depends(area_any_status("company"))]


async def _read(file: UploadFile) -> bytes:
    return await file.read(service.MAX_BYTES + 1)


@router.post("/images")
async def upload_company_image(
    ctx: CompanyCtx, file: Annotated[UploadFile, File()], kind: str = "logo"
) -> dict[str, Any]:
    """Saved under ``vip/<company-slug>/<kind>/``. Works during sign-up too."""
    return await service.save_company_image(ctx.org.slug, kind, await _read(file))


@router.post("/presentation")
async def upload_presentation(ctx: CompanyCtx, file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    """The company presentation (PDF up to 20 MB), shown on the public profile."""
    data = await file.read(service.PRESENTATION_MAX_MB * 1024 * 1024 + 1)
    info = await service.save_presentation(ctx.org, data, file.filename or "")
    return {k: v for k, v in info.items() if k != "key"}


@router.delete("/presentation")
async def delete_presentation(ctx: CompanyCtx) -> dict[str, bool]:
    await service.remove_presentation(ctx.org)
    return {"ok": True}


@admin_router.post("/images")
async def upload_platform_image(
    admin: AdminUser, file: Annotated[UploadFile, File()], kind: str = "event"
) -> dict[str, Any]:
    return await service.save_platform_image(kind, await _read(file))


@public_router.get("/{key:path}", include_in_schema=False)
async def serve(key: str) -> Response:
    obj = await storage.get(key)
    if obj is None:
        raise NotFound("Imagem não encontrada.", code="media_not_found")
    extra = {"Content-Disposition": "inline"} if obj.content_type == "application/pdf" else {}
    return Response(
        obj.data,
        media_type=obj.content_type,
        headers={
            **extra,
            # keys are unique per upload: the content never changes
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )

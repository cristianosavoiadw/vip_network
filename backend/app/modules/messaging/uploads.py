"""Chat attachments (scope §12, §28 "controle de anexos").

Files live in the bucket (``app.core.storage``) under ``<company-slug>/chat/<uuid>`` with a JSON
sidecar ``<uuid>.json`` (id, org, uploader, name, size, mime). No table: a message references
the file by
``data.upload_id``. A file is served only to the uploader's company or to readers of a
conversation that has a message referencing it.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.modules.auth.deps import Ctx, DbSession, area
from app.modules.messaging.models import Conversation, Message
from app.modules.organizations.models import Organization

router = APIRouter(tags=["messaging"])

MsgCtx = Annotated[Ctx, Depends(area("messages"))]

# extension -> (mime, magic check)
ALLOWED: dict[str, str] = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "csv": "text/csv",
}
INLINE = ("image/png", "image/jpeg", "image/webp", "application/pdf")
CHUNK = 1024 * 256


class TooLarge(AppError):
    status_code = 413
    code = "file_too_large"


def _safe_id(value: Any) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError):
        return None


def file_key(slug: str, upload_id: str) -> str:
    return f"{slug}/chat/{upload_id}"


async def _slug(session: AsyncSession, org_id: uuid.UUID | str) -> str | None:
    oid = _safe_id(org_id)
    if oid is None:
        return None
    org = await session.get(Organization, uuid.UUID(oid))
    return org.slug if org else None


async def read_meta(
    session: AsyncSession, org_id: uuid.UUID | str, upload_id: Any
) -> dict[str, Any] | None:
    """Sidecar of a file uploaded by ``org_id`` (None when missing or of another company)."""
    uid = _safe_id(upload_id)
    oid = _safe_id(org_id)
    slug = await _slug(session, org_id) if oid else None
    if uid is None or oid is None or slug is None:
        return None
    sidecar = await storage.get(file_key(slug, uid) + ".json")
    if sidecar is None or not await storage.exists(file_key(slug, uid)):
        return None
    try:
        meta = json.loads(sidecar.data.decode("utf-8"))
    except ValueError:
        return None
    if meta.get("org_id") != oid or meta.get("id") != uid:
        return None
    return meta


def _magic_ok(ext: str, head: bytes) -> bool:
    if ext == "pdf":
        return head.startswith(b"%PDF")
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext in ("xlsx", "docx"):
        return head.startswith(b"PK\x03\x04")
    if ext == "csv":
        return b"\x00" not in head
    return False


def _clean_name(name: str) -> str:
    name = PurePosixPath(name.replace("\\", "/")).name
    keep = "".join(c for c in name if c.isprintable() and c not in '<>:"/\\|?*')
    return keep.strip()[:180] or "arquivo"


@router.post("/uploads")
async def upload(file: UploadFile, ctx: MsgCtx) -> dict[str, Any]:
    name = _clean_name(file.filename or "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise AppError(
            "Tipo de arquivo não aceito. Envie PDF, imagem (PNG, JPG, WEBP), planilha (XLSX, CSV) "
            "ou documento (DOCX).",
            code="file_type",
        )
    max_bytes = get_settings().upload_max_mb * 1024 * 1024
    uid = str(uuid.uuid4())
    parts: list[bytes] = []
    size = 0
    while chunk := await file.read(CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise TooLarge(
                f"O arquivo passa de {get_settings().upload_max_mb} MB.",
                details={"max_mb": get_settings().upload_max_mb},
            )
        parts.append(chunk)
    data = b"".join(parts)
    if size == 0:
        raise AppError("O arquivo está vazio.", code="file_empty")
    if not _magic_ok(ext, data[:16]):
        raise AppError("O conteúdo do arquivo não confere com o tipo.", code="file_type")
    key = file_key(ctx.org.slug, uid)
    await storage.put(key, data, ALLOWED[ext])
    meta = {
        "id": uid,
        "org_id": str(ctx.org_id),
        "user_id": str(ctx.user_id),
        "name": name,
        "size": size,
        "mime": ALLOWED[ext],
        "created_at": datetime.now(UTC).isoformat(),
    }
    await storage.put(
        key + ".json", json.dumps(meta, ensure_ascii=False).encode("utf-8"), "application/json"
    )
    return {
        "id": uid,
        "name": name,
        "size": size,
        "mime": meta["mime"],
        "url": f"/api/v1/uploads/{uid}",
    }


async def _find(session: DbSession, ctx: Ctx, upload_id: str) -> dict[str, Any] | None:
    meta = await read_meta(session, ctx.org_id, upload_id)
    if meta is not None:
        return meta
    from app.modules.messaging import service

    rows = (
        await session.execute(
            select(Message, Conversation)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.kind == "attachment",
                Message.data["upload_id"].astext == upload_id,
                (Conversation.org_low_id == ctx.org_id) | (Conversation.org_high_id == ctx.org_id),
            )
        )
    ).all()
    for msg, conv in rows:
        if msg.sender_org_id is None or not service.can_read(conv, ctx.user):
            continue
        if await service.opps.is_blocked(session, conv.org_low_id, conv.org_high_id):
            continue
        meta = await read_meta(session, msg.sender_org_id, upload_id)
        if meta is not None:
            return meta
    return None


@router.get("/uploads/{upload_id}")
async def download(upload_id: str, ctx: MsgCtx, session: DbSession) -> Response:
    uid = _safe_id(upload_id)
    meta = await _find(session, ctx, uid) if uid else None
    slug = await _slug(session, meta["org_id"]) if meta else None
    obj = await storage.get(file_key(slug, meta["id"])) if meta and slug else None
    if meta is None or obj is None:
        raise NotFound("Arquivo não encontrado.", code="upload_not_found")
    disposition = "inline" if meta["mime"] in INLINE else "attachment"
    return Response(
        obj.data,
        media_type=meta["mime"],
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(meta['name'])}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
        },
    )

"""Images of companies and of the platform, stored in the bucket (owner decision 2026-11-14).

Every image is checked (PNG, JPG or WebP by content, at most 5 MB), resized to the size of its
use and saved as WebP under ``<company-slug>/<kind>/<uuid>.webp`` (company images) or
``vip-network/<kind>/<uuid>.webp`` (events, mentors). The URL returned is the API path that
serves it: ``/api/v1/media/<key>``.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core import storage
from app.core.errors import AppError

MAX_BYTES = 5 * 1024 * 1024
# kind -> (max width, max height, square crop?)
COMPANY_KINDS: dict[str, tuple[int, int, bool]] = {
    "logo": (512, 512, False),
    "cover": (1920, 720, False),
    "offer": (1600, 1600, False),
    "avatar": (400, 400, True),
}
PLATFORM_KINDS: dict[str, tuple[int, int, bool]] = {
    "event": (1600, 1000, False),
    "mentor": (800, 800, False),
    "site": (1920, 1200, False),
}
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
MEDIA_PREFIX = "/api/v1/media/"


def url_for(key: str) -> str:
    return MEDIA_PREFIX + key


def key_from_url(url: str) -> str | None:
    return url[len(MEDIA_PREFIX) :] if url.startswith(MEDIA_PREFIX) else None


def process(data: bytes, kind: str, *, platform: bool = False) -> bytes:
    sizes = PLATFORM_KINDS if platform else COMPANY_KINDS
    if kind not in sizes:
        raise AppError("Tipo de imagem inválido.", code="image_kind")
    if not data:
        raise AppError("O arquivo está vazio.", code="file_empty")
    if len(data) > MAX_BYTES:
        raise AppError("A imagem pode ter no máximo 5 MB.", code="file_too_large")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise AppError("Envie uma imagem PNG, JPG ou WebP.", code="file_type") from exc
    if fmt not in ALLOWED_FORMATS:
        raise AppError("Envie uma imagem PNG, JPG ou WebP.", code="file_type")
    img = ImageOps.exif_transpose(img)
    max_w, max_h, square = sizes[kind]
    if square:
        img = ImageOps.fit(img, (max_w, max_h))
    else:
        img.thumbnail((max_w, max_h))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=86, method=4)
    return out.getvalue()


async def save_company_image(slug: str, kind: str, data: bytes) -> dict[str, str]:
    webp = process(data, kind)
    key = f"{slug}/{kind}/{uuid.uuid4().hex}.webp"
    await storage.put(key, webp, "image/webp")
    return {"key": key, "url": url_for(key)}


async def save_platform_image(kind: str, data: bytes) -> dict[str, str]:
    webp = process(data, kind, platform=True)
    key = f"{storage.PLATFORM_PREFIX}/{kind}/{uuid.uuid4().hex}.webp"
    await storage.put(key, webp, "image/webp")
    return {"key": key, "url": url_for(key)}


# ------------------------------------------------------------------ company presentation (PDF)

PRESENTATION_MAX_MB = 20


def clean_filename(name: str) -> str:
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    keep = "".join(c for c in base if c.isprintable() and c not in '<>:"/\\|?*').strip()
    if not keep.lower().endswith(".pdf"):
        keep = (keep or "apresentacao") + ".pdf"
    return keep[:180]


async def save_presentation(org: Any, data: bytes, filename: str) -> dict[str, Any]:
    """Store the company's presentation PDF at <slug>/apresentacao/<uuid>.pdf and point the
    profile to it; the previous file is removed."""
    from datetime import UTC, datetime

    if not data:
        raise AppError("O arquivo está vazio.", code="file_empty")
    if len(data) > PRESENTATION_MAX_MB * 1024 * 1024:
        raise AppError(
            f"A apresentação pode ter no máximo {PRESENTATION_MAX_MB} MB.", code="file_too_large"
        )
    if not data.startswith(b"%PDF"):
        raise AppError("Envie a apresentação em PDF.", code="file_type")
    key = f"{org.slug}/apresentacao/{uuid.uuid4().hex}.pdf"
    await storage.put(key, data, "application/pdf")
    old = (org.presentation or {}).get("key")
    org.presentation = {
        "key": key,
        "url": url_for(key),
        "name": clean_filename(filename),
        "size": len(data),
        "uploaded_at": datetime.now(UTC).isoformat(),
    }
    if old and old != key:
        await storage.delete(old)
    return org.presentation


async def remove_presentation(org: Any) -> None:
    old = (org.presentation or {}).get("key")
    org.presentation = {}
    if old:
        await storage.delete(old)

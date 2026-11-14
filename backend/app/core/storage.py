"""Object storage for images and attachments (owner decision 2026-11-14).

Bucket ``vip`` (``VIP_S3_BUCKET``) on MinIO/S3, keys ``<company-slug>/<kind>/<file>``; the
platform's own images use ``vip-network/<kind>/<file>``. Without ``VIP_S3_ENDPOINT`` the same keys
are written under ``upload_dir`` on local disk (tests, machines without MinIO).

Files are never served straight from MinIO: the API streams them (``/api/v1/media/...``), so the
storage needs no public domain and access rules stay in one place.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR, get_settings

log = logging.getLogger("vip.storage")
SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,250}$")
PLATFORM_PREFIX = "vip-network"


class StorageError(Exception):
    pass


@dataclass(frozen=True)
class StoredObject:
    data: bytes
    content_type: str


def valid_key(key: str) -> bool:
    return bool(SAFE_KEY.match(key)) and ".." not in key and not key.endswith("/")


def _s3_enabled() -> bool:
    return bool(get_settings().s3_endpoint)


@lru_cache
def _client() -> Any:
    import boto3
    from botocore.config import Config

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        config=Config(
            signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 3}
        ),
    )


def _local_root() -> Path:
    configured = get_settings().upload_dir
    return Path(configured) if configured else BASE_DIR / "data" / "uploads"


def _local_path(key: str) -> Path:
    return _local_root() / key


_bucket_ready = False


async def ensure_bucket() -> None:
    """Create the bucket on first use (idempotent)."""
    global _bucket_ready
    if _bucket_ready or not _s3_enabled():
        return
    bucket = get_settings().s3_bucket

    def run() -> None:
        from botocore.exceptions import ClientError

        c = _client()
        try:
            c.head_bucket(Bucket=bucket)
        except ClientError:
            c.create_bucket(Bucket=bucket)

    await asyncio.to_thread(run)
    _bucket_ready = True


async def put(key: str, data: bytes, content_type: str) -> None:
    if not valid_key(key):
        raise StorageError(f"invalid key {key!r}")
    if _s3_enabled():
        await ensure_bucket()
        await asyncio.to_thread(
            _client().put_object,
            Bucket=get_settings().s3_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, data)
    await asyncio.to_thread(path.with_name(path.name + ".ctype").write_text, content_type, "utf-8")


async def get(key: str) -> StoredObject | None:
    if not valid_key(key):
        return None
    if _s3_enabled():
        from botocore.exceptions import ClientError

        def run() -> StoredObject | None:
            try:
                obj = _client().get_object(Bucket=get_settings().s3_bucket, Key=key)
            except ClientError:
                return None
            return StoredObject(
                obj["Body"].read(), obj.get("ContentType") or "application/octet-stream"
            )

        return await asyncio.to_thread(run)
    path = _local_path(key)
    if not path.is_file():
        return None
    ctype_file = path.with_name(path.name + ".ctype")
    ctype = ctype_file.read_text("utf-8") if ctype_file.is_file() else "application/octet-stream"
    return StoredObject(await asyncio.to_thread(path.read_bytes), ctype)


async def exists(key: str) -> bool:
    if not valid_key(key):
        return False
    if _s3_enabled():
        from botocore.exceptions import ClientError

        def run() -> bool:
            try:
                _client().head_object(Bucket=get_settings().s3_bucket, Key=key)
                return True
            except ClientError:
                return False

        return await asyncio.to_thread(run)
    return _local_path(key).is_file()


async def delete(key: str) -> None:
    if not valid_key(key):
        return
    if _s3_enabled():
        await asyncio.to_thread(_client().delete_object, Bucket=get_settings().s3_bucket, Key=key)
        return
    path = _local_path(key)
    path.unlink(missing_ok=True)
    path.with_name(path.name + ".ctype").unlink(missing_ok=True)


async def check() -> str:
    """For ``manage.py check``: where files go."""
    s = get_settings()
    if not _s3_enabled():
        return f"disco local ({_local_root()})"
    await ensure_bucket()
    return f"MinIO {s.s3_endpoint} · bucket {s.s3_bucket}"

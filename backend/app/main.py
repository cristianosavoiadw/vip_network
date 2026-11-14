"""VIP Network API. Run with ``uv run python manage.py runserver`` (port 3399).

Every module in ``MODULES`` has a ``router.py`` exposing ``router`` (company area and public
routes) and optionally ``admin_router`` (team panel, under ``/admin``) and ``public_router``.
Adding a module = one line in ``MODULES``.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.session import engine

settings = get_settings()
logging.basicConfig(level=settings.log_level)

MODULES = (
    "auth",
    "organizations",
    "catalog",
    "discovery",
    "likes",
    "matches",
    "connections",
    "opportunities",
    "messaging",
    "events",
    "mentorship",
    "intelligence",
    "weos",
    "billing",
    "boosts",
    "invites",
    "notifications",
    "media",
    "mail",
    "analytics",
    "admin",
    "dashboard",
)

# background loops: "module.path:function" (each runs forever, catching its own errors)
BACKGROUND = (
    "app.modules.mail.service:tick_forever",
    "app.modules.invites.service:tick_forever",
    "app.modules.billing.service:tick_forever",
    "app.modules.weos.jobs:tick_forever",
    "app.modules.messaging.service:tick_forever",
    "app.modules.events.service:tick_forever",
    "app.modules.boosts.service:tick_forever",
)


def _load(path: str):  # noqa: ANN202
    mod, _, attr = path.partition(":")
    try:
        return getattr(importlib.import_module(mod), attr)
    except (ImportError, AttributeError):
        return None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    tasks = []
    for path in BACKGROUND:
        fn = _load(path)
        if fn is not None:
            tasks.append(asyncio.create_task(fn()))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()


app = FastAPI(
    title="VIP Network API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

api = APIRouter(prefix="/api/v1")
for name in MODULES:
    try:
        module = importlib.import_module(f"app.modules.{name}.router")
    except ModuleNotFoundError as exc:
        if exc.name == f"app.modules.{name}.router":
            continue
        raise
    for attr in ("public_router", "router", "admin_router"):
        r = getattr(module, attr, None)
        if r is not None:
            api.include_router(r)
app.include_router(api)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["ops"])
async def ready() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}

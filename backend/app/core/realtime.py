"""In-memory pub/sub for the authenticated WebSocket (one API instance; Redis pub/sub when
the API scales out). Payloads are small dicts: {"type": "notification" | "message" | ..., ...}.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any

_queues: dict[uuid.UUID, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)


def subscribe(user_id: uuid.UUID) -> asyncio.Queue[dict[str, Any]]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
    _queues[user_id].add(q)
    return q


def unsubscribe(user_id: uuid.UUID, q: asyncio.Queue[dict[str, Any]]) -> None:
    _queues[user_id].discard(q)
    if not _queues[user_id]:
        _queues.pop(user_id, None)


def publish(user_id: uuid.UUID, payload: dict[str, Any]) -> None:
    for q in list(_queues.get(user_id, ())):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


def online(user_id: uuid.UUID) -> bool:
    return bool(_queues.get(user_id))

"""Release import lock held by the API when enqueueing."""

from __future__ import annotations

import redis

from config import get_settings

_LOCK_PREFIX = "partifi:import_lock:"


def release_import_lock(partset_id: str) -> None:
    client = redis.from_url(get_settings().redis_url, decode_responses=True)
    client.delete(f"{_LOCK_PREFIX}{partset_id}")

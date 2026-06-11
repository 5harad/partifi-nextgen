"""Release gen_parts lock held by the API when enqueueing."""

from __future__ import annotations

import redis

from config import get_settings

_LOCK_PREFIX = "partifi:gen_parts_lock:"


def release_gen_parts_lock(partset_id: str) -> None:
    client = redis.from_url(get_settings().redis_url, decode_responses=True)
    client.delete(f"{_LOCK_PREFIX}{partset_id}")

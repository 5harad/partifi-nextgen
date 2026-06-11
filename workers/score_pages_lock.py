"""Release score_pages lock held by the API when enqueueing warm_score_pages."""

from __future__ import annotations

import redis

from config import get_settings

_LOCK_PREFIX = "partifi:score_pages_lock:"


def release_score_pages_lock(score_id: str) -> None:
    client = redis.from_url(get_settings().redis_url, decode_responses=True)
    client.delete(f"{_LOCK_PREFIX}{score_id}")

"""Read rotated partset page cache warm errors from Redis."""

from __future__ import annotations

from app.services.queue import get_redis

_ERROR_PREFIX = "partifi:partset_cache_error:"
_CACHE_ERROR_TTL = 3600


def get_partset_cache_error(partset_id: str) -> str | None:
    value = get_redis().get(f"{_ERROR_PREFIX}{partset_id}")
    if not value:
        return None
    return str(value)


def clear_partset_cache_error(partset_id: str) -> None:
    get_redis().delete(f"{_ERROR_PREFIX}{partset_id}")

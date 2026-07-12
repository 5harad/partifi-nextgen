"""Redis-backed rotated page cache warm errors (non-fatal to the partset pipeline)."""

from __future__ import annotations

import redis

from config import get_settings

_ERROR_PREFIX = "partifi:partset_cache_error:"
_MAX_MESSAGE_LEN = 512


def _key(partset_id: str) -> str:
    return f"{_ERROR_PREFIX}{partset_id}"


def _ttl_seconds() -> int:
    settings = get_settings()
    return max(settings.job_timeout_seconds + 300, 600)


def _client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def _normalize_message(message: str | None) -> str:
    normalized = " ".join(str(message or "Failed to prepare rotated page images").split())
    if len(normalized) <= _MAX_MESSAGE_LEN:
        return normalized
    return normalized[: _MAX_MESSAGE_LEN - 3] + "..."


def set_partset_cache_error(partset_id: str, message: str | None) -> None:
    client = _client()
    client.set(_key(partset_id), _normalize_message(message), ex=_ttl_seconds())


def get_partset_cache_error(partset_id: str) -> str | None:
    value = _client().get(_key(partset_id))
    if not value:
        return None
    return str(value)


def clear_partset_cache_error(partset_id: str) -> None:
    _client().delete(_key(partset_id))

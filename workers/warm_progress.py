"""Redis-backed convert progress for warm_score_pages jobs."""

from __future__ import annotations

import redis

from config import get_settings

_PROGRESS_PREFIX = "partifi:warm_progress:"


def _key(score_id: str) -> str:
    return f"{_PROGRESS_PREFIX}{score_id}"


def _ttl_seconds() -> int:
    settings = get_settings()
    return max(settings.job_timeout_seconds + 300, 600)


def _client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def reset_warm_progress(score_id: str) -> None:
    client = _client()
    client.set(_key(score_id), "0", ex=_ttl_seconds())


def add_warm_progress(score_id: str, increment: float) -> None:
    client = _client()
    key = _key(score_id)
    client.incrbyfloat(key, increment)
    client.expire(key, _ttl_seconds())


def set_warm_progress(score_id: str, value: float) -> None:
    client = _client()
    client.set(_key(score_id), str(min(100.0, max(0.0, value))), ex=_ttl_seconds())


def clear_warm_progress(score_id: str) -> None:
    _client().delete(_key(score_id))

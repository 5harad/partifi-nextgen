"""Prevent concurrent warm_score_pages jobs for the same score."""

from __future__ import annotations

from app.config import get_settings
from app.services.queue import get_redis

_LOCK_PREFIX = "partifi:score_pages_lock:"


def _lock_key(score_id: str) -> str:
    return f"{_LOCK_PREFIX}{score_id}"


def try_acquire_score_pages_lock(score_id: str) -> bool:
    settings = get_settings()
    ttl = max(settings.job_timeout_seconds + 300, 600)
    return bool(get_redis().set(_lock_key(score_id), "1", nx=True, ex=ttl))


def release_score_pages_lock(score_id: str) -> None:
    get_redis().delete(_lock_key(score_id))

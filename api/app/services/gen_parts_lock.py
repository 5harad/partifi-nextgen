"""Prevent concurrent gen_parts jobs for the same partset."""

from __future__ import annotations

from app.config import get_settings
from app.services.queue import get_redis

_LOCK_PREFIX = "partifi:gen_parts_lock:"


def _lock_key(partset_id: str) -> str:
    return f"{_LOCK_PREFIX}{partset_id}"


def try_acquire_gen_parts_lock(partset_id: str) -> bool:
    settings = get_settings()
    ttl = max(settings.job_timeout_seconds + 300, 600)
    return bool(get_redis().set(_lock_key(partset_id), "1", nx=True, ex=ttl))


def release_gen_parts_lock(partset_id: str) -> None:
    get_redis().delete(_lock_key(partset_id))

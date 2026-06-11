"""Read warm_score_pages convert progress from Redis."""

from __future__ import annotations

from app.services.queue import get_redis

_PROGRESS_PREFIX = "partifi:warm_progress:"


def get_warm_progress(score_id: str) -> float:
    value = get_redis().get(f"{_PROGRESS_PREFIX}{score_id}")
    if value is None:
        return 0.0
    try:
        return min(100.0, max(0.0, float(value)))
    except ValueError:
        return 0.0

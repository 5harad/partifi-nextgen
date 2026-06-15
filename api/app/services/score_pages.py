"""Score page PNG availability (local cache or warm-from-PDF)."""

from __future__ import annotations

from app.services.local_cache import get_local_cache
from app.services.queue import enqueue_job
from app.services.score_pages_lock import (
    release_score_pages_lock,
    try_acquire_score_pages_lock,
)
from app.services.warm_progress import get_warm_progress, reset_warm_progress


def score_pages_available(score_id: str) -> bool:
    return get_local_cache().score_has_pages(score_id)


def ensure_score_pages_warming(score_id: str) -> dict[str, bool | float]:
    """Return image status; enqueue warm_score_pages when needed."""
    if score_pages_available(score_id):
        return {"images_ready": True, "images_warming": False, "image_progress": 100.0}

    progress = get_warm_progress(score_id)
    if progress >= 100.0:
        # Warm job finished (or failed) but page PNGs are still missing — retry.
        release_score_pages_lock(score_id)
        reset_warm_progress(score_id)
        if try_acquire_score_pages_lock(score_id):
            enqueue_job("warm_score_pages", {"score_id": score_id})
            progress = 0.0
    elif try_acquire_score_pages_lock(score_id):
        enqueue_job("warm_score_pages", {"score_id": score_id})

    return {
        "images_ready": False,
        "images_warming": True,
        "image_progress": progress,
    }

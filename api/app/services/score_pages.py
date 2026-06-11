"""Score page PNG availability (local cache, S3, or warm-from-PDF)."""

from __future__ import annotations

from app.services.local_cache import get_local_cache
from app.services.queue import enqueue_job
from app.services.s3 import score_page_images_on_s3
from app.services.score_pages_lock import try_acquire_score_pages_lock
from app.services.warm_progress import get_warm_progress


def score_pages_available(score_id: str) -> bool:
    cache = get_local_cache()
    if cache.score_has_pages(score_id):
        return True
    return score_page_images_on_s3(score_id)


def ensure_score_pages_warming(score_id: str) -> dict[str, bool | float]:
    """Return image status; enqueue warm_score_pages when needed."""
    if score_pages_available(score_id):
        return {"images_ready": True, "images_warming": False, "image_progress": 100.0}

    if try_acquire_score_pages_lock(score_id):
        enqueue_job("warm_score_pages", {"score_id": score_id})

    return {
        "images_ready": False,
        "images_warming": True,
        "image_progress": get_warm_progress(score_id),
    }

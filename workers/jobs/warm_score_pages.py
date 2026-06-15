"""Enqueue warm_score_pages jobs."""

from __future__ import annotations

import logging

from local_cache import get_local_cache
from score_page_cache import build_score_page_cache
from score_pages_lock import release_score_pages_lock
from warm_progress import reset_warm_progress, set_warm_progress

logger = logging.getLogger("partifi.warm_score_pages")


def run_warm_score_pages(score_id: str, *, job_id: str | None = None) -> None:
    suffix = job_id or "unknown"
    try:
        cache = get_local_cache()
        if cache.score_has_pages(score_id):
            logger.info("Score %s page images already cached", score_id)
            return

        reset_warm_progress(score_id)
        build_score_page_cache(score_id, job_id=suffix)
        set_warm_progress(score_id, 100.0)
    except Exception:
        logger.exception("Failed to warm page images for score %s", score_id)
        raise
    finally:
        release_score_pages_lock(score_id)

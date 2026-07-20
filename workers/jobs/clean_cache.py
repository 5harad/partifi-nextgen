"""Evict stale local cache and job scratch directories."""

from __future__ import annotations

import logging
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import db_conn
from config import get_settings
from local_cache import get_local_cache
from pipeline.local_cache import LocalCache

logger = logging.getLogger("partifi.clean_cache")


def _invalidate_completed_parts(partset_id: str) -> None:
    """Clear completed-generation state when its cached PDFs are evicted."""
    db_conn.execute(
        """
        UPDATE partsets
        SET status = 'analysis',
            parts_ready = 0,
            cut_start = NULL,
            cut_complete = NULL,
            cut_progress = 0,
            paste_start = NULL,
            paste_complete = NULL,
            paste_progress = 0
        WHERE id = :id AND parts_ready = 1
        """,
        {"id": partset_id},
    )


def _evict_by_ttl(cache: LocalCache, *, category: str, ttl_days: int) -> int:
    cutoff = time.time() - ttl_days * 86400
    base = cache.root / category
    if not base.is_dir():
        return 0
    removed = 0
    for path in list(base.iterdir()):
        if not path.is_dir():
            continue
        if path.stat().st_mtime >= cutoff:
            continue
        if category == "parts":
            _invalidate_completed_parts(path.name)
        shutil.rmtree(path, ignore_errors=True)
        removed += 1
        logger.info("Evicted %s cache for %s (TTL %dd)", category, path.name, ttl_days)
    return removed


def _evict_cold_scores(cache: LocalCache, ttl_days: int) -> int:
    cutoff = datetime.utcnow() - timedelta(days=ttl_days)
    rows = db_conn.fetchall(
        """
        SELECT s.id AS score_id, MAX(p.last_access) AS last_access
        FROM scores s
        JOIN partsets p ON p.score_id = s.id
        WHERE s.s3 = 1
        GROUP BY s.id
        HAVING last_access IS NULL OR last_access < :cutoff
        """,
        {"cutoff": cutoff},
    )
    removed = 0
    for row in rows:
        score_root = cache.score_root(row.score_id)
        if score_root.is_dir():
            shutil.rmtree(score_root, ignore_errors=True)
            removed += 1
            logger.info("Evicted score cache for %s", row.score_id)
    return removed


def _evict_to_size_cap(cache: LocalCache, max_bytes: int) -> int:
    usage = cache.disk_usage_bytes()
    if usage <= max_bytes:
        return 0

    removed = 0
    entries = sorted(cache.iter_cache_dirs(), key=lambda item: item[2])
    for category, path, _mtime in entries:
        if cache.disk_usage_bytes() <= int(max_bytes * 0.9):
            break
        if category == "parts":
            _invalidate_completed_parts(path.name)
        shutil.rmtree(path, ignore_errors=True)
        removed += 1
        logger.info("Evicted %s cache for %s (size cap)", category, path.name)
    return removed


def run_clean_cache() -> None:
    settings = get_settings()
    cache = get_local_cache()

    scratch_removed = LocalCache.clean_stale_scratch(
        Path("/tmp/partifi"),
        max_age_hours=settings.partifi_cache_scratch_max_age_hours,
    )
    if scratch_removed:
        logger.info("Removed %d stale job scratch dirs", scratch_removed)

    preview_removed = _evict_by_ttl(
        cache, category="preview", ttl_days=settings.partifi_cache_preview_ttl_days
    )
    parts_removed = _evict_by_ttl(
        cache, category="parts", ttl_days=settings.partifi_cache_parts_ttl_days
    )
    scores_removed = _evict_cold_scores(cache, settings.partifi_cache_score_ttl_days)

    max_bytes = int(settings.partifi_cache_max_gb * 1024**3)
    cap_removed = _evict_to_size_cap(cache, max_bytes)

    usage_gb = cache.disk_usage_bytes() / 1024**3
    logger.info(
        "Cache cleanup done: preview=%d parts=%d scores=%d cap=%d usage=%.2fGB",
        preview_removed,
        parts_removed,
        scores_removed,
        cap_removed,
        usage_gb,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_clean_cache()

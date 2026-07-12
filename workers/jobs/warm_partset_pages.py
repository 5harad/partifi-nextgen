"""Rebuild rotated partset page PNGs in local cache (no re-analysis)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from import_lock import release_import_lock
from jobs.reorient_partset import rebuild_partset_page_cache
from partset_cache_status import clear_partset_cache_error, set_partset_cache_error
from pipeline.partset_orientation import normalize_rotation_degrees, partset_uses_custom_pages

logger = logging.getLogger("partifi.warm_partset_pages")


def run_warm_partset_pages(
    partset_id: str,
    score_id: str,
    rotation_degrees: int,
    *,
    job_id: str | None = None,
) -> None:
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    if not partset_uses_custom_pages(rotation_degrees):
        return

    suffix = job_id or "unknown"
    workdir = Path(f"/tmp/partifi/{partset_id}/warm-pages-{suffix}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        logger.info(
            "Warming rotated page cache for partset %s (rotation=%s)",
            partset_id,
            rotation_degrees,
        )
        rebuild_partset_page_cache(
            partset_id,
            score_id,
            rotation_degrees,
            workdir=workdir,
            job_id=job_id,
        )
        clear_partset_cache_error(partset_id)
        logger.info("Rotated page cache warm complete for partset %s", partset_id)
    except Exception as exc:
        logger.exception("Rotated page cache warm failed for partset %s", partset_id)
        set_partset_cache_error(partset_id, str(exc))
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        release_import_lock(partset_id)

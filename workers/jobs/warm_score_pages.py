"""Build local page PNG cache from an S3 PDF (legacy scores without PNGs on S3)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from local_cache import get_local_cache
from pdf2png import par_pdf2png
from s3_storage import download_file, download_prefix, score_images_exist, score_pdf_s3_key
from score_pages_lock import release_score_pages_lock
from warm_progress import reset_warm_progress, set_warm_progress

logger = logging.getLogger("partifi.warm_score_pages")

SCORE_KINDS = ("lowres", "highres", "thumbs")


def _hydrate_from_s3(score_id: str) -> None:
    cache = get_local_cache()
    for kind in SCORE_KINDS:
        dest = cache.score_kind_dir(score_id, kind)
        dest.mkdir(parents=True, exist_ok=True)
        download_prefix(f"scores/{score_id}/{kind}/", dest)


def run_warm_score_pages(score_id: str, *, job_id: str | None = None) -> None:
    suffix = job_id or "unknown"
    workdir = Path(f"/tmp/partifi/warm-{score_id}-{suffix}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        cache = get_local_cache()
        if cache.score_has_pages(score_id):
            logger.info("Score %s page images already cached", score_id)
            return

        reset_warm_progress(score_id)

        if score_images_exist(score_id):
            logger.info("Hydrating score %s page images from S3", score_id)
            set_warm_progress(score_id, 50.0)
            _hydrate_from_s3(score_id)
            set_warm_progress(score_id, 100.0)
            return

        pdf_path = workdir / "score.pdf"
        logger.info("Converting score %s PDF to local page images", score_id)
        download_file(score_pdf_s3_key(score_id), pdf_path)

        pages_dir = workdir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        par_pdf2png(str(pdf_path), str(pages_dir), None, score_id=score_id)
        cache.copy_pages_tree(score_id, pages_dir)
        set_warm_progress(score_id, 100.0)
        logger.info("Score %s page images ready in local cache", score_id)
    except Exception:
        logger.exception("Failed to warm page images for score %s", score_id)
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        release_score_pages_lock(score_id)

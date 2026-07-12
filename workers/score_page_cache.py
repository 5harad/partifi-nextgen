"""Build local page PNG cache from an S3 score PDF."""

from __future__ import annotations

import glob
import logging
import shutil
from pathlib import Path

import db_conn
from local_cache import get_local_cache
from pdf2png import par_pdf2png
from pdf_validate_repair import ensure_valid_score_pdf
from pipeline.page_dimensions import Orientation
from score_cache import fetch_score_orientation

logger = logging.getLogger("partifi.score_page_cache")


def build_score_page_cache(score_id: str, *, job_id: str | None = None) -> None:
    """Convert the score PDF into local page PNGs when highres cache is empty."""
    cache = get_local_cache()
    if cache.score_has_kind(score_id, "highres"):
        return

    suffix = job_id or "warm"
    workdir = Path(f"/tmp/partifi/warm-{score_id}-{suffix}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        pdf_path = workdir / "score.pdf"
        logger.info("Converting score %s PDF to local page images", score_id)
        shutil.copy2(cache.ensure_score_pdf(score_id), pdf_path)
        ensure_valid_score_pdf(pdf_path, workdir)

        pages_dir = workdir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        stored = fetch_score_orientation(score_id)
        orientation: Orientation = "landscape" if stored == "landscape" else "portrait"
        orientation = par_pdf2png(
            str(pdf_path),
            str(pages_dir),
            None,
            score_id=score_id,
            orientation=orientation,
        )
        cache.copy_pages_tree(score_id, pages_dir)
        num_pages = len(glob.glob(str(pages_dir / "lowres" / "*.png")))
        db_conn.execute(
            "UPDATE scores SET convert_start = COALESCE(convert_start, NOW()), "
            "convert_complete = NOW(), num_pages = :num_pages, orientation = :orientation, s3 = 1 "
            "WHERE id = :id",
            {"num_pages": num_pages, "orientation": orientation, "id": score_id},
        )
        logger.info("Score %s page images ready in local cache", score_id)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

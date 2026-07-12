"""Build local page PNG cache from an S3 score PDF."""

from __future__ import annotations

import glob
import logging
import shutil
from pathlib import Path

import db_conn
from local_cache import get_local_cache
from pdf2png import par_pdf2png
from pipeline.orientation_probe import infer_orientation_from_pdf
from pipeline.pdf_validate import validate_downloaded_pdf
from s3_storage import download_file, score_pdf_s3_key

logger = logging.getLogger("partifi.score_page_cache")


def build_score_page_cache(score_id: str, *, job_id: str | None = None) -> None:
    """Convert the score PDF from S3 into local page PNGs when cache is empty."""
    cache = get_local_cache()
    if cache.score_has_pages(score_id):
        return

    suffix = job_id or "warm"
    workdir = Path(f"/tmp/partifi/warm-{score_id}-{suffix}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        pdf_path = workdir / "score.pdf"
        logger.info("Converting score %s PDF to local page images", score_id)
        download_file(score_pdf_s3_key(score_id), pdf_path)
        validate_downloaded_pdf(pdf_path)

        pages_dir = workdir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        orientation = infer_orientation_from_pdf(pdf_path)
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

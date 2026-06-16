"""Import pipeline: convert PDF to PNGs and analyze segments."""

from __future__ import annotations

import glob
import logging
import shutil
from pathlib import Path

from find_segments import analyze_score
from local_cache import ensure_lowres_files, get_local_cache
from pdf2png import convert_score
from pipeline.pdf_validate import validate_downloaded_pdf
from s3_storage import download_file, score_pdf_s3_key
from score_cache import (
    copy_partset_segs_to_score,
    copy_score_segs_to_partset,
    score_analysis_complete,
)

from import_lock import release_import_lock
from jobs.errors import mark_partset_error

import db_conn

logger = logging.getLogger("partifi.import_pipeline")


def _mark_convert_complete(partset_id: str, score_id: str, num_pages: int | None = None) -> None:
    db_conn.execute(
        "UPDATE partsets SET status = 'convert', convert_start = NOW(), "
        "convert_complete = NOW(), convert_progress = 100 WHERE id = :id",
        {"id": partset_id},
    )
    if num_pages is None:
        row = db_conn.fetchone(
            "SELECT num_pages FROM scores WHERE id = :id",
            {"id": score_id},
        )
        num_pages = int(row.num_pages) if row and row.num_pages else None
    if num_pages is not None:
        db_conn.execute(
            "UPDATE scores SET convert_start = COALESCE(convert_start, NOW()), "
            "convert_complete = NOW(), num_pages = :num_pages, s3 = 1 WHERE id = :id",
            {"num_pages": num_pages, "id": score_id},
        )
    else:
        db_conn.execute(
            "UPDATE scores SET convert_start = COALESCE(convert_start, NOW()), "
            "convert_complete = NOW(), s3 = 1 WHERE id = :id",
            {"id": score_id},
        )


def _score_pages_available(score_id: str) -> bool:
    return get_local_cache().score_has_pages(score_id)


def _run_convert(partset_id: str, score_id: str, workdir: Path) -> int:
    pdf_path = workdir / "score.pdf"
    logger.info("Downloading score %s for partset %s", score_id, partset_id)
    download_file(score_pdf_s3_key(score_id), pdf_path)
    validate_downloaded_pdf(pdf_path)

    pages_dir = workdir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Converting PDF for partset %s", partset_id)
    convert_score(partset_id, pdf_path, pages_dir)

    logger.info("Caching page images for score %s", score_id)
    get_local_cache().copy_pages_tree(score_id, pages_dir)

    lowres_files = sorted(glob.glob(str(pages_dir / "lowres" / "*.png")))
    num_pages = len(lowres_files)
    db_conn.execute(
        "UPDATE scores SET convert_start = COALESCE(convert_start, NOW()), "
        "convert_complete = NOW(), num_pages = :num_pages, s3 = 1 WHERE id = :id",
        {"num_pages": num_pages, "id": score_id},
    )
    return num_pages


def run_import_pipeline(partset_id: str, score_id: str, *, job_id: str | None = None) -> None:
    suffix = job_id or "unknown"
    workdir = Path(f"/tmp/partifi/{partset_id}/import-{suffix}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        if _score_pages_available(score_id):
            logger.info("Reusing existing page images for score %s", score_id)
            _mark_convert_complete(partset_id, score_id)
        else:
            _run_convert(partset_id, score_id, workdir)

        if score_analysis_complete(score_id):
            logger.info("Reusing cached segment analysis for score %s", score_id)
            copy_score_segs_to_partset(score_id, partset_id)
        else:
            lowres_files = [str(p) for p in ensure_lowres_files(score_id)]
            logger.info("Analyzing %d pages for partset %s", len(lowres_files), partset_id)
            analyze_score(partset_id, lowres_files)
            copy_partset_segs_to_score(partset_id, score_id)

        db_conn.execute(
            "UPDATE partsets SET last_access = NOW() WHERE id = :id",
            {"id": partset_id},
        )
        logger.info("Import pipeline complete for partset %s", partset_id)
    except Exception as exc:
        logger.exception("Import pipeline failed for partset %s", partset_id)
        mark_partset_error(partset_id, message=str(exc), job_id=job_id)
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        release_import_lock(partset_id)

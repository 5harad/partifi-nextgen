"""Import pipeline: convert PDF to PNGs and analyze segments."""

from __future__ import annotations

import glob
import hashlib
import logging
import shutil
from pathlib import Path

from find_segments import analyze_score
from local_cache import ensure_lowres_files, get_local_cache
from pdf2png import convert_score
from pdf_validate_repair import ensure_valid_score_pdf
from pipeline.orientation_probe import infer_orientation_from_pdf
from pipeline.page_dimensions import Orientation
from pipeline.pdf_validate import PDF_CORRUPT_MESSAGE
from score_cache import (
    copy_partset_segs_to_score,
    copy_score_segs_to_partset,
    invalidate_score_analysis,
    score_analysis_complete,
)
from score_limits import ScoreTooLargeError
from score_pdf_refetch import repair_corrupt_score_pdf

from import_lock import release_import_lock
from jobs.errors import mark_partset_error

import db_conn

logger = logging.getLogger("partifi.import_pipeline")


def _fetch_score_import_state(score_id: str):
    return db_conn.fetchone(
        "SELECT convert_complete, orientation FROM scores WHERE id = :id",
        {"id": score_id},
    )


def _fetch_score_file_hash(score_id: str) -> str | None:
    row = db_conn.fetchone(
        "SELECT file_hash FROM scores WHERE id = :id",
        {"id": score_id},
    )
    if not row or not row.file_hash:
        return None
    return str(row.file_hash)


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


def _sha1_file(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _refetch_from_imslp(score_id: str, pdf_path: Path, workdir: Path) -> Path:
    try:
        return repair_corrupt_score_pdf(score_id, pdf_path, workdir)
    except ScoreTooLargeError:
        raise
    except ValueError as repair_exc:
        raise ValueError(PDF_CORRUPT_MESSAGE) from repair_exc


def _ensure_score_pdf(score_id: str, workdir: Path) -> Path:
    """Load score PDF from cache/S3; refetch from IMSLP only when the archive is bad."""
    pdf_path = workdir / "score.pdf"
    cache = get_local_cache()

    cached = cache.ensure_score_pdf(score_id)
    shutil.copy2(cached, pdf_path)
    # Hash archive bytes before ensure_valid_score_pdf may Ghostscript-rewrite pdf_path.
    local_hash = _sha1_file(pdf_path)
    try:
        ensure_valid_score_pdf(pdf_path, workdir)
        return pdf_path
    except ValueError:
        pass

    db_hash = _fetch_score_file_hash(score_id)
    if db_hash and local_hash == db_hash:
        logger.warning(
            "Archived PDF for score %s failed validation (matches DB hash); "
            "attempting IMSLP refetch",
            score_id,
        )
        return _refetch_from_imslp(score_id, pdf_path, workdir)

    logger.warning(
        "Cached PDF for score %s failed validation and differs from DB hash; "
        "reloading from S3",
        score_id,
    )
    cache.score_pdf_path(score_id).unlink(missing_ok=True)
    cached = cache.ensure_score_pdf(score_id)
    shutil.copy2(cached, pdf_path)
    try:
        ensure_valid_score_pdf(pdf_path, workdir)
        return pdf_path
    except ValueError:
        logger.warning(
            "S3 PDF for score %s failed validation; attempting IMSLP refetch",
            score_id,
        )
        return _refetch_from_imslp(score_id, pdf_path, workdir)


def _run_convert(
    partset_id: str,
    score_id: str,
    workdir: Path,
    pdf_path: Path,
    orientation: Orientation,
) -> int:
    pages_dir = workdir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Converting PDF for partset %s (orientation=%s)", partset_id, orientation)
    detected = convert_score(partset_id, pdf_path, pages_dir, orientation=orientation)

    logger.info("Caching page images for score %s", score_id)
    get_local_cache().copy_pages_tree(score_id, pages_dir)

    lowres_files = sorted(glob.glob(str(pages_dir / "lowres" / "*.png")))
    num_pages = len(lowres_files)
    db_conn.execute(
        "UPDATE scores SET convert_start = COALESCE(convert_start, NOW()), "
        "convert_complete = NOW(), num_pages = :num_pages, orientation = :orientation, s3 = 1 "
        "WHERE id = :id",
        {"num_pages": num_pages, "orientation": detected, "id": score_id},
    )
    return num_pages


def _run_analysis(partset_id: str, score_id: str) -> None:
    if score_analysis_complete(score_id):
        logger.info("Reusing cached segment analysis for score %s", score_id)
        copy_score_segs_to_partset(score_id, partset_id)
        return

    lowres_files = [str(p) for p in ensure_lowres_files(score_id)]
    logger.info("Analyzing %d pages for partset %s", len(lowres_files), partset_id)
    analyze_score(partset_id, lowres_files)
    copy_partset_segs_to_score(partset_id, score_id)


def run_import_pipeline(partset_id: str, score_id: str, *, job_id: str | None = None) -> None:
    suffix = job_id or "unknown"
    workdir = Path(f"/tmp/partifi/{partset_id}/import-{suffix}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        pdf_path = _ensure_score_pdf(score_id, workdir)
        inferred = infer_orientation_from_pdf(pdf_path)
        score_state = _fetch_score_import_state(score_id)
        stored = str(score_state.orientation or "portrait") if score_state else "portrait"
        first_time = not score_state or score_state.convert_complete is None
        mismatch = not first_time and inferred != stored
        cache_warm = _score_pages_available(score_id)

        if mismatch:
            logger.info(
                "Orientation mismatch for score %s: stored=%s inferred=%s",
                score_id,
                stored,
                inferred,
            )
            invalidate_score_analysis(score_id)
            get_local_cache().invalidate_score_pages(score_id)
            cache_warm = False

        need_convert = first_time or mismatch or not cache_warm
        if need_convert:
            convert_orientation: Orientation = inferred if first_time or mismatch else stored
            _run_convert(partset_id, score_id, workdir, pdf_path, convert_orientation)
        else:
            logger.info("Reusing existing page images for score %s", score_id)
            _mark_convert_complete(partset_id, score_id)

        _run_analysis(partset_id, score_id)

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

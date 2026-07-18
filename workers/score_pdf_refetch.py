"""Re-download an IMSLP-backed score PDF when the archived copy is unusable."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import db_conn
from imslp_client import download_imslp_pdf
from local_cache import get_local_cache
from pdf_validate_repair import ensure_valid_score_pdf
from pipeline.orientation_probe import infer_orientation_from_pdf
from pipeline.pdf_validate import PDF_CORRUPT_MESSAGE
from s3_storage import score_pdf_s3_key, upload_file
from score_cache import invalidate_score_analysis

logger = logging.getLogger("partifi.score_pdf_refetch")


def _fetch_score(score_id: str):
    return db_conn.fetchone(
        "SELECT id, imslp_id, file_size, file_hash FROM scores WHERE id = :id",
        {"id": score_id},
    )


def replace_score_pdf_from_imslp(
    score_id: str,
    dest: Path,
    workdir: Path,
    *,
    imslp_id: str | None = None,
    force_replace: bool = False,
) -> bool:
    """Download IMSLP PDF, validate, write to dest.

    Uploads to S3 and resets score convert/analysis only when ``force_replace``
    is set or the new SHA-1 differs from ``scores.file_hash``.

    Returns True after a successful archive replacement.

    Raises:
        ValueError: score missing, no imslp_id, downloaded PDF invalid, or
            (when not ``force_replace``) the download hash matches the archived hash.
    """
    row = _fetch_score(score_id)
    if not row:
        raise ValueError(f"Score not found: {score_id}")

    resolved_imslp = imslp_id or row.imslp_id
    if not resolved_imslp:
        raise ValueError(f"Score {score_id} has no imslp_id")

    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Downloading IMSLP %s for score %s (was %s bytes, hash=%s)",
        resolved_imslp,
        score_id,
        row.file_size,
        row.file_hash,
    )
    size = download_imslp_pdf(resolved_imslp, dest)
    ensure_valid_score_pdf(dest, workdir)
    orientation = infer_orientation_from_pdf(dest)

    pdf_bytes = dest.read_bytes()
    file_hash = hashlib.sha1(pdf_bytes).hexdigest()
    logger.info(
        "Downloaded %s bytes, sha1=%s, orientation=%s",
        size,
        file_hash,
        orientation,
    )

    hash_changed = file_hash != (row.file_hash or "")
    if not force_replace and not hash_changed:
        raise ValueError(PDF_CORRUPT_MESSAGE)

    upload_file(dest, score_pdf_s3_key(score_id), "application/pdf")
    db_conn.execute(
        """
        UPDATE scores SET
            imslp_id = :imslp_id,
            file_size = :file_size,
            file_hash = :file_hash,
            s3 = 1,
            convert_start = NULL,
            convert_complete = NULL,
            num_pages = NULL,
            orientation = :orientation,
            analysis_start = NULL,
            analysis_complete = NULL
        WHERE id = :id
        """,
        {
            "id": score_id,
            "imslp_id": resolved_imslp,
            "file_size": size,
            "file_hash": file_hash,
            "orientation": orientation,
        },
    )
    invalidate_score_analysis(score_id)
    get_local_cache().invalidate_score(score_id)
    logger.info(
        "Replaced %s on S3 (orientation=%s); invalidated local cache and score analysis",
        score_pdf_s3_key(score_id),
        orientation,
    )
    return True


def repair_corrupt_score_pdf(score_id: str, dest: Path, workdir: Path) -> Path:
    """One-shot IMSLP refetch after the archived PDF failed validation.

    Only replaces the archive when the downloaded file's hash differs.
    """
    row = _fetch_score(score_id)
    if not row:
        raise ValueError(f"Score not found: {score_id}")
    if not row.imslp_id:
        raise ValueError(PDF_CORRUPT_MESSAGE)

    logger.warning(
        "Archived PDF for score %s failed validation; refetching IMSLP %s",
        score_id,
        row.imslp_id,
    )
    replace_score_pdf_from_imslp(
        score_id,
        dest,
        workdir,
        imslp_id=str(row.imslp_id),
        force_replace=False,
    )
    return dest

"""Re-download a score PDF from IMSLP and replace the archived S3 object.

Usage (on EC2, from repo root):

  docker compose -f docker-compose.prod.yml exec worker-1 \\
    python refetch_score_pdf.py --score-id hMGHC --confirm

  docker compose -f docker-compose.prod.yml exec worker-1 \\
    python refetch_score_pdf.py --score-id hMGHC --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import sys
from pathlib import Path

import db_conn
from imslp_client import download_imslp_pdf
from local_cache import get_local_cache
from pdf_validate_repair import ensure_valid_score_pdf
from pipeline.pdf_validate import validate_downloaded_pdf
from s3_storage import score_pdf_s3_key, upload_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("partifi.refetch_score_pdf")


def _fetch_score(score_id: str):
    return db_conn.fetchone(
        "SELECT id, imslp_id, file_size, file_hash FROM scores WHERE id = :id",
        {"id": score_id},
    )


def refetch_score_pdf(
    score_id: str,
    *,
    imslp_id: str | None = None,
    dry_run: bool = False,
) -> None:
    row = _fetch_score(score_id)
    if not row:
        raise SystemExit(f"Score not found: {score_id}")

    resolved_imslp = imslp_id or row.imslp_id
    if not resolved_imslp:
        raise SystemExit(f"Score {score_id} has no imslp_id; pass --imslp-id")

    workdir = Path(f"/tmp/partifi/refetch-{score_id}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    pdf_path = workdir / "score.pdf"

    try:
        logger.info(
            "Downloading IMSLP %s for score %s (was %s bytes, hash=%s)",
            resolved_imslp,
            score_id,
            row.file_size,
            row.file_hash,
        )
        size = download_imslp_pdf(resolved_imslp, pdf_path)
        ensure_valid_score_pdf(pdf_path, workdir)
        validate_downloaded_pdf(pdf_path)

        pdf_bytes = pdf_path.read_bytes()
        file_hash = hashlib.sha1(pdf_bytes).hexdigest()
        logger.info(
            "Downloaded %s bytes, sha1=%s, %%EOF=%s",
            size,
            file_hash,
            b"%%EOF" in pdf_bytes,
        )

        if dry_run:
            logger.info("Dry run: would upload to %s and update scores row", score_pdf_s3_key(score_id))
            return

        upload_file(pdf_path, score_pdf_s3_key(score_id), "application/pdf")
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
                orientation = 'portrait',
                analysis_start = NULL,
                analysis_complete = NULL
            WHERE id = :id
            """,
            {
                "id": score_id,
                "imslp_id": resolved_imslp,
                "file_size": size,
                "file_hash": file_hash,
            },
        )
        get_local_cache().invalidate_score(score_id)
        logger.info("Replaced %s on S3 and invalidated local cache", score_pdf_s3_key(score_id))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Re-download a score PDF from IMSLP")
    parser.add_argument("--score-id", required=True)
    parser.add_argument("--imslp-id", help="IMSLP work id (default: scores.imslp_id)")
    parser.add_argument("--dry-run", action="store_true", help="Download and validate only")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Upload to S3 and update DB (required unless --dry-run)",
    )
    args = parser.parse_args(argv)

    if not args.dry_run and not args.confirm:
        raise SystemExit("Pass --confirm to upload, or --dry-run to test download")

    refetch_score_pdf(
        args.score_id,
        imslp_id=args.imslp_id,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

"""Download a score from IMSLP and run the import pipeline."""

from __future__ import annotations

import hashlib
import logging
import random
import shutil
import string
from pathlib import Path

from import_lock import release_import_lock
from imslp_client import download_imslp_pdf
from jobs.errors import mark_partset_error
from jobs.import_pipeline import run_import_pipeline
from s3_storage import score_pdf_s3_key, upload_file

import db_conn

logger = logging.getLogger("partifi.imslp_import")

PDF_MAGIC = b"%PDF"
MAX_BYTES = 60_000_000
_CHARS = string.ascii_letters + string.digits


def _gen_score_id() -> str:
    while True:
        candidate = "".join(random.choice(_CHARS) for _ in range(5))
        row = db_conn.fetchone("SELECT id FROM scores WHERE id = :id", {"id": candidate})
        if not row:
            return candidate


def _set_import_progress(partset_id: str, progress: float) -> None:
    db_conn.execute(
        "UPDATE partsets SET import_progress = :progress WHERE id = :id",
        {"progress": progress, "id": partset_id},
    )


def _mark_import_error(partset_id: str) -> None:
    mark_partset_error(partset_id, "import")

def run_imslp_import(partset_id: str, imslp_id: str, *, job_id: str | None = None) -> None:
    suffix = job_id or "unknown"
    workdir = Path(f"/tmp/partifi/{partset_id}/import-{suffix}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    pdf_path = workdir / "score.pdf"

    try:
        logger.info("Downloading IMSLP %s for partset %s", imslp_id, partset_id)
        download_imslp_pdf(
            imslp_id,
            pdf_path,
            on_progress=lambda progress: _set_import_progress(partset_id, progress),
        )

        pdf_bytes = pdf_path.read_bytes()
        if not pdf_bytes.startswith(PDF_MAGIC):
            logger.error("IMSLP %s did not return a PDF for partset %s", imslp_id, partset_id)
            _mark_import_error(partset_id)
            return
        if len(pdf_bytes) > MAX_BYTES:
            logger.error("IMSLP %s exceeds size limit for partset %s", imslp_id, partset_id)
            _mark_import_error(partset_id)
            return

        file_hash = hashlib.sha1(pdf_bytes).hexdigest()
        file_size = len(pdf_bytes)

        existing = db_conn.fetchone(
            "SELECT id, imslp_id FROM scores WHERE file_hash = :hash",
            {"hash": file_hash},
        )
        if existing:
            score_id = existing.id
            if imslp_id and not existing.imslp_id:
                db_conn.execute(
                    "UPDATE scores SET imslp_id = :imslp_id WHERE id = :id",
                    {"imslp_id": imslp_id, "id": score_id},
                )
        else:
            score_id = _gen_score_id()
            db_conn.execute(
                "INSERT INTO scores "
                "(id, imslp_id, file_hash, file_size, import_start, import_complete, num_downloads, s3) "
                "VALUES (:id, :imslp_id, :hash, :size, NOW(), NOW(), 0, 0)",
                {
                    "id": score_id,
                    "imslp_id": imslp_id,
                    "hash": file_hash,
                    "size": file_size,
                },
            )
            upload_file(pdf_path, score_pdf_s3_key(score_id), "application/pdf")

        db_conn.execute(
            "UPDATE partsets SET score_id = :score_id, import_complete = NOW(), import_progress = 100 "
            "WHERE id = :id",
            {"score_id": score_id, "id": partset_id},
        )

        run_import_pipeline(partset_id, score_id)
    except Exception:
        logger.exception("IMSLP import failed for partset %s", partset_id)
        _mark_import_error(partset_id)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        release_import_lock(partset_id)

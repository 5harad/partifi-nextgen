"""Resolve IMSLP edition PDF URLs and check file size."""

from __future__ import annotations

import hashlib
import logging

import httpx
from sqlalchemy.orm import Session

from app.models import Score
from app.score_limits import MAX_SCORE_BYTES, ScoreTooLargeError
from app.services.s3 import score_pdf_s3_key, upload_bytes
from app.utils.ids import gen_score_id
from pipeline.imslp_download import (
    IMSLP_COOKIES,
    IMSLP_HEADERS,
    log_imslp_http_failure,
    mirror_request_cookies,
    resolve_imslp_pdf_url_with_retries,
)

REQUEST_TIMEOUT = 30.0
PDF_MAGIC = b"%PDF"

logger = logging.getLogger(__name__)

__all__ = [
    "check_imslp_pdf_size",
    "ingest_imslp_pdf_bytes",
    "resolve_imslp_pdf_for_import",
]


def _imslp_http_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT,
        cookies=IMSLP_COOKIES,
        headers=IMSLP_HEADERS,
    )


def resolve_imslp_pdf_for_import(
    imslp_id: str,
    *,
    client: httpx.Client | None = None,
) -> tuple[str, bytes | None]:
    """Resolve an IMSLP PDF once (with retries). Returns (pdf_url, inline_bytes|None)."""
    owns_client = client is None
    if owns_client:
        client = _imslp_http_client()

    try:
        assert client is not None
        try:
            pdf_url, cached = resolve_imslp_pdf_url_with_retries(imslp_id, client)
        except ValueError as exc:
            logger.warning(
                "IMSLP %s PDF URL resolution failed during pre-import check: %s",
                imslp_id,
                exc,
            )
            raise
        except httpx.HTTPError as exc:
            log_imslp_http_failure(
                exc,
                imslp_id=imslp_id,
                operation="pre_import_pdf_resolve",
                level=logging.ERROR,
            )
            raise

        if cached is not None:
            if len(cached) > MAX_SCORE_BYTES:
                raise ScoreTooLargeError(len(cached))
            return pdf_url, cached

        head = client.head(
            pdf_url,
            follow_redirects=True,
            cookies=mirror_request_cookies(pdf_url),
        )
        head.raise_for_status()
        content_length = head.headers.get("content-length")
        if content_length and int(content_length) > MAX_SCORE_BYTES:
            raise ScoreTooLargeError(int(content_length))
        return pdf_url, None
    finally:
        if owns_client:
            client.close()


def check_imslp_pdf_size(imslp_id: str, *, client: httpx.Client | None = None) -> None:
    """Raise ScoreTooLargeError when the IMSLP edition PDF exceeds the limit."""
    resolve_imslp_pdf_for_import(imslp_id, client=client)


def ingest_imslp_pdf_bytes(db: Session, imslp_id: str, pdf_bytes: bytes) -> tuple[str, str]:
    """Store IMSLP PDF bytes (dedupe by hash). Returns (score_id, action)."""
    if not pdf_bytes.startswith(PDF_MAGIC):
        raise ValueError("File is not a valid PDF")
    if len(pdf_bytes) > MAX_SCORE_BYTES:
        raise ScoreTooLargeError(len(pdf_bytes))

    file_hash = hashlib.sha1(pdf_bytes).hexdigest()
    existing = db.query(Score).filter(Score.file_hash == file_hash).first()
    if existing:
        if imslp_id and not existing.imslp_id:
            existing.imslp_id = imslp_id
        return existing.id, "continue"

    from datetime import datetime

    score_id = gen_score_id(db)
    now = datetime.utcnow()
    db.add(
        Score(
            id=score_id,
            imslp_id=imslp_id,
            file_hash=file_hash,
            file_size=len(pdf_bytes),
            num_downloads=0,
            s3=False,
            import_start=now,
            import_complete=now,
        )
    )
    upload_bytes(score_pdf_s3_key(score_id), pdf_bytes, "application/pdf")
    return score_id, "upload"

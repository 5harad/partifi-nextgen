"""Resolve IMSLP edition PDF URLs and check file size."""

from __future__ import annotations

import logging

import httpx

from app.score_limits import MAX_SCORE_BYTES, ScoreTooLargeError
from pipeline.imslp_download import (
    IMSLP_COOKIES,
    IMSLP_HEADERS,
    mirror_request_cookies,
    resolve_imslp_pdf_url,
)

REQUEST_TIMEOUT = 30.0

logger = logging.getLogger(__name__)

__all__ = ["check_imslp_pdf_size", "resolve_imslp_pdf_url"]


def check_imslp_pdf_size(imslp_id: str, *, client: httpx.Client | None = None) -> None:
    """Raise ScoreTooLargeError when the IMSLP edition PDF exceeds the limit."""
    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
            cookies=IMSLP_COOKIES,
            headers=IMSLP_HEADERS,
        )

    try:
        assert client is not None
        try:
            pdf_url, cached = resolve_imslp_pdf_url(imslp_id, client)
        except ValueError as exc:
            logger.warning(
                "IMSLP %s PDF URL resolution failed during pre-import check: %s",
                imslp_id,
                exc,
            )
            raise

        if cached is not None:
            if len(cached) > MAX_SCORE_BYTES:
                raise ScoreTooLargeError(len(cached))
            return

        head = client.head(
            pdf_url,
            follow_redirects=True,
            cookies=mirror_request_cookies(pdf_url),
        )
        head.raise_for_status()
        content_length = head.headers.get("content-length")
        if content_length and int(content_length) > MAX_SCORE_BYTES:
            raise ScoreTooLargeError(int(content_length))
    finally:
        if owns_client:
            client.close()

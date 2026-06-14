"""Download PDFs from IMSLP."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from pipeline.imslp_download import (
    IMSLP_COOKIES,
    IMSLP_HEADERS,
    IMSLP_RETRY_ATTEMPTS,
    IMSLP_RETRY_BASE_SECONDS,
    mirror_request_cookies,
    resolve_imslp_pdf_url_with_retries,
)
from score_limits import MAX_SCORE_BYTES, ScoreTooLargeError

TIMEOUT = 120.0

logger = logging.getLogger(__name__)

__all__ = ["download_imslp_pdf", "download_imslp_pdf_url"]


def _is_retryable_download_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (403, 429) or code >= 500
    return False


def download_imslp_pdf_url(
    pdf_url: str,
    dest: Path,
    client: httpx.Client,
    *,
    on_progress: Callable[[float], None] | None = None,
    max_attempts: int = IMSLP_RETRY_ATTEMPTS,
) -> int:
    """Stream-download a resolved mirror PDF URL with retries."""
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        downloaded = 0
        try:
            with client.stream(
                "GET",
                pdf_url,
                cookies=mirror_request_cookies(pdf_url),
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0) or 0)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        downloaded += len(chunk)
                        if downloaded > MAX_SCORE_BYTES:
                            raise ScoreTooLargeError(downloaded)
                        handle.write(chunk)
                        if on_progress and total > 0:
                            on_progress(round(downloaded / total * 100))
            return downloaded
        except Exception as exc:
            last_exc = exc
            dest.unlink(missing_ok=True)
            if isinstance(exc, ScoreTooLargeError):
                raise
            if not _is_retryable_download_error(exc):
                raise
            if attempt + 1 >= max_attempts:
                break
            delay = IMSLP_RETRY_BASE_SECONDS * (3**attempt) + random.uniform(0, 1)
            logger.warning(
                "IMSLP PDF download attempt %d/%d failed for %s, retry in %.1fs: %s",
                attempt + 1,
                max_attempts,
                pdf_url,
                delay,
                exc,
            )
            time.sleep(delay)
    assert last_exc is not None
    logger.warning("IMSLP PDF download failed after %d attempts: %s", max_attempts, pdf_url)
    raise last_exc


def download_imslp_pdf(
    imslp_id: str,
    dest: Path,
    *,
    pdf_url: str | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> int:
    downloaded = 0

    with httpx.Client(
        follow_redirects=True,
        timeout=TIMEOUT,
        cookies=IMSLP_COOKIES,
        headers=IMSLP_HEADERS,
    ) as client:
        if pdf_url:
            return download_imslp_pdf_url(
                pdf_url,
                dest,
                client,
                on_progress=on_progress,
            )

        resolved_url, cached = resolve_imslp_pdf_url_with_retries(imslp_id, client)
        if cached is not None:
            if len(cached) > MAX_SCORE_BYTES:
                raise ScoreTooLargeError(len(cached))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(cached)
            if on_progress:
                on_progress(100.0)
            return len(cached)

        return download_imslp_pdf_url(
            resolved_url,
            dest,
            client,
            on_progress=on_progress,
        )

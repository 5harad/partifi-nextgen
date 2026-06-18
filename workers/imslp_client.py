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
    fetch_mirror_pdf,
    log_imslp_http_failure,
    resolve_imslp_pdf_url_with_retries,
)
from score_limits import MAX_SCORE_BYTES, ScoreTooLargeError, reject_score_too_large

TIMEOUT = 120.0

logger = logging.getLogger(__name__)

__all__ = ["download_imslp_pdf", "download_imslp_pdf_url"]


def _is_retryable_download_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
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
    """Download a resolved mirror PDF URL, following disclaimer chains with retries."""
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            _, content = fetch_mirror_pdf(client, pdf_url)
            if len(content) > MAX_SCORE_BYTES:
                raise reject_score_too_large(
                    len(content),
                    logger=logger,
                )
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            if on_progress:
                on_progress(100.0)
            return len(content)
        except Exception as exc:
            last_exc = exc
            dest.unlink(missing_ok=True)
            if isinstance(exc, ScoreTooLargeError):
                raise
            if not _is_retryable_download_error(exc):
                log_imslp_http_failure(
                    exc,
                    url=pdf_url,
                    operation="pdf_download",
                    level=logging.ERROR,
                )
                raise
            if attempt + 1 >= max_attempts:
                break
            delay = IMSLP_RETRY_BASE_SECONDS * (3**attempt) + random.uniform(0, 1)
            log_imslp_http_failure(
                exc,
                url=pdf_url,
                operation=f"pdf_download attempt {attempt + 1}/{max_attempts}",
            )
            logger.warning(
                "IMSLP PDF download retry in %.1fs url=%s",
                delay,
                pdf_url,
            )
            time.sleep(delay)
    assert last_exc is not None
    log_imslp_http_failure(
        last_exc,
        url=pdf_url,
        operation=f"pdf_download failed after {max_attempts} attempts",
        level=logging.ERROR,
    )
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
                raise reject_score_too_large(
                    len(cached),
                    logger=logger,
                    imslp_id=imslp_id,
                )
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

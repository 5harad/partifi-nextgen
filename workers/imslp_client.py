"""Download PDFs from IMSLP."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx

from pipeline.imslp_download import (
    IMSLP_COOKIES,
    IMSLP_HEADERS,
    mirror_request_cookies,
    resolve_imslp_pdf_url,
)
from score_limits import MAX_SCORE_BYTES, ScoreTooLargeError

TIMEOUT = 120.0

__all__ = ["download_imslp_pdf", "resolve_imslp_pdf_url"]


def download_imslp_pdf(
    imslp_id: str,
    dest: Path,
    *,
    on_progress: Callable[[float], None] | None = None,
) -> int:
    downloaded = 0

    with httpx.Client(
        follow_redirects=True,
        timeout=TIMEOUT,
        cookies=IMSLP_COOKIES,
        headers=IMSLP_HEADERS,
    ) as client:
        pdf_url, cached = resolve_imslp_pdf_url(imslp_id, client)
        if cached is not None:
            if len(cached) > MAX_SCORE_BYTES:
                raise ScoreTooLargeError(len(cached))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(cached)
            if on_progress:
                on_progress(100.0)
            return len(cached)

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

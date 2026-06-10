"""Download PDFs from IMSLP."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from pathlib import Path

import httpx

IMSLP_INDEX_URL = "https://imslp.org/wiki/Special:ImagefromIndex/{imslp_id}"
IMSLP_COOKIES = {
    "imslpdisclaimeraccepted": "yes",
    "redirectPassed": "1",
}
IMSLP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
MAX_BYTES = 60_000_000
TIMEOUT = 120.0


def resolve_imslp_pdf_url(imslp_id: str, client: httpx.Client) -> str:
    page_url = IMSLP_INDEX_URL.format(imslp_id=imslp_id)
    response = client.get(page_url)
    response.raise_for_status()

    match = re.search(r'id="sm_dl_wait"\s+data-id="([^"]+)"', response.text)
    if not match:
        match = re.search(r'data-id="(https?://[^"]+\.pdf[^"]*)"', response.text, re.I)
    if not match:
        raise ValueError(f"Could not resolve PDF URL for IMSLP {imslp_id}")

    pdf_url = html.unescape(match.group(1))
    if not pdf_url.lower().endswith(".pdf"):
        raise ValueError(f"Resolved URL is not a PDF for IMSLP {imslp_id}")
    return pdf_url


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
        pdf_url = resolve_imslp_pdf_url(imslp_id, client)
        with client.stream("GET", pdf_url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0) or 0)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as handle:
                for chunk in response.iter_bytes():
                    downloaded += len(chunk)
                    if downloaded > MAX_BYTES:
                        raise ValueError("File exceeds 60 MB limit")
                    handle.write(chunk)
                    if on_progress and total > 0:
                        on_progress(round(downloaded / total * 100))

    return downloaded

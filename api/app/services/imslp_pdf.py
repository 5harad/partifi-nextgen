"""Resolve IMSLP edition PDF URLs and check file size."""

from __future__ import annotations

import html
import re

import httpx

from app.score_limits import MAX_SCORE_BYTES, ScoreTooLargeError

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
REQUEST_TIMEOUT = 30.0


def _pdf_response_from_redirect(response: httpx.Response) -> tuple[str, bytes] | None:
    url = str(response.url)
    if not url.lower().endswith(".pdf"):
        content_type = response.headers.get("content-type", "").lower()
        if "application/pdf" not in content_type and response.content[:4] != b"%PDF":
            return None
    return url, response.content


def resolve_imslp_pdf_url(imslp_id: str, client: httpx.Client) -> tuple[str, bytes | None]:
    page_url = IMSLP_INDEX_URL.format(imslp_id=imslp_id)
    response = client.get(page_url)
    response.raise_for_status()

    direct = _pdf_response_from_redirect(response)
    if direct:
        return direct

    match = re.search(r'id="sm_dl_wait"\s+data-id="([^"]+)"', response.text)
    if not match:
        match = re.search(r'data-id="(https?://[^"]+\.pdf[^"]*)"', response.text, re.I)
    if not match:
        raise ValueError(f"Could not resolve PDF URL for IMSLP {imslp_id}")

    pdf_url = html.unescape(match.group(1))
    if not pdf_url.lower().endswith(".pdf"):
        raise ValueError(f"Resolved URL is not a PDF for IMSLP {imslp_id}")
    return pdf_url, None


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
        pdf_url, cached = resolve_imslp_pdf_url(imslp_id, client)
        if cached is not None:
            if len(cached) > MAX_SCORE_BYTES:
                raise ScoreTooLargeError(len(cached))
            return

        head = client.head(pdf_url, follow_redirects=True)
        head.raise_for_status()
        content_length = head.headers.get("content-length")
        if content_length and int(content_length) > MAX_SCORE_BYTES:
            raise ScoreTooLargeError(int(content_length))
    finally:
        if owns_client:
            client.close()

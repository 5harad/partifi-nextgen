"""Shared IMSLP / mirror PDF URL resolution and download helpers."""

from __future__ import annotations

import html
import logging
import random
import re
import time

import httpx

logger = logging.getLogger(__name__)

IMSLP_RETRY_ATTEMPTS = 3
IMSLP_RETRY_BASE_SECONDS = 5.0

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
PML_MIRROR_DISCLAIMER_COOKIE = "disclaimer_bypass"
PML_MIRROR_DISCLAIMER_VALUE = "OK"
# Backward-compatible aliases (PML Asia tests / callers).
PMLASIA_DISCLAIMER_COOKIE = PML_MIRROR_DISCLAIMER_COOKIE
PMLASIA_DISCLAIMER_VALUE = PML_MIRROR_DISCLAIMER_VALUE


def is_pdf_body(content: bytes, content_type: str = "") -> bool:
    if len(content) >= 4 and content[:4] == b"%PDF":
        return True
    return "application/pdf" in content_type.lower()


def mirror_request_cookies(url: str) -> dict[str, str]:
    """PML mirror hosts require a disclaimer cookie before serving PDF bytes."""
    lowered = url.lower()
    if "imslp.tw" in lowered or "petruccilibrary.us" in lowered:
        return {PML_MIRROR_DISCLAIMER_COOKIE: PML_MIRROR_DISCLAIMER_VALUE}
    return {}


def is_pmlasia_disclaimer(page_html: str) -> bool:
    return "PMLASIA_DOWNLOAD_TARGET" in page_html or "pmlasiaDisclaimer" in page_html


def parse_pmlasia_pdf_url(page_html: str, page_url: str) -> str | None:
    match = re.search(r'PMLASIA_DOWNLOAD_TARGET\s*=\s*"([^"]+)"', page_html)
    if not match:
        match = re.search(r'href="(uploads/[^"]+\.pdf)"', page_html, re.I)
    if not match:
        return None
    path = html.unescape(match.group(1).replace("\\/", "/"))
    return str(httpx.URL(page_url).join(path))


def pdf_response_from_redirect(response: httpx.Response) -> tuple[str, bytes] | None:
    """Return PDF url+body when a redirect lands on real PDF bytes (not an HTML interstitial)."""
    content_type = response.headers.get("content-type", "")
    if not is_pdf_body(response.content, content_type):
        return None
    return str(response.url), response.content


def is_pmlus_disclaimer(page_html: str, page_url: str = "") -> bool:
    if "petruccilibrary.us" in page_url.lower():
        return True
    return "Petrucci Music Library US" in page_html


def parse_pmlus_pdf_url(page_html: str, page_url: str) -> str | None:
    match = re.search(r'href="(files/[^"]+\.pdf)"', page_html, re.I)
    if not match:
        return None
    path = html.unescape(match.group(1))
    return str(httpx.URL(page_url).join(path))


def _fetch_mirror_disclaimer_pdf(
    client: httpx.Client,
    disclaimer_html: str,
    page_url: str,
    *,
    pdf_url: str | None,
    mirror_name: str,
) -> tuple[str, bytes]:
    if not pdf_url:
        raise ValueError(f"Could not parse {mirror_name} disclaimer page at {page_url}")

    response = client.get(pdf_url, cookies=mirror_request_cookies(pdf_url))
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if not is_pdf_body(response.content, content_type):
        raise ValueError(f"{mirror_name} mirror did not return a PDF at {pdf_url}")
    return str(response.url), response.content


def _fetch_pmlasia_pdf(
    client: httpx.Client, disclaimer_html: str, page_url: str
) -> tuple[str, bytes]:
    return _fetch_mirror_disclaimer_pdf(
        client,
        disclaimer_html,
        page_url,
        pdf_url=parse_pmlasia_pdf_url(disclaimer_html, page_url),
        mirror_name="PML Asia",
    )


def _fetch_pmlus_pdf(
    client: httpx.Client, disclaimer_html: str, page_url: str
) -> tuple[str, bytes]:
    return _fetch_mirror_disclaimer_pdf(
        client,
        disclaimer_html,
        page_url,
        pdf_url=parse_pmlus_pdf_url(disclaimer_html, page_url),
        mirror_name="PML-US",
    )


def resolve_imslp_pdf_url(imslp_id: str, client: httpx.Client) -> tuple[str, bytes | None]:
    page_url = IMSLP_INDEX_URL.format(imslp_id=imslp_id)
    response = client.get(page_url)
    response.raise_for_status()

    direct = pdf_response_from_redirect(response)
    if direct:
        return direct

    page_url = str(response.url)
    if is_pmlasia_disclaimer(response.text):
        return _fetch_pmlasia_pdf(client, response.text, page_url)

    if is_pmlus_disclaimer(response.text, page_url):
        return _fetch_pmlus_pdf(client, response.text, page_url)

    match = re.search(r'id="sm_dl_wait"\s+data-id="([^"]+)"', response.text)
    if not match:
        match = re.search(r'data-id="(https?://[^"]+\.pdf[^"]*)"', response.text, re.I)
    if not match:
        page_html = response.text
        logger.info(
            "IMSLP %s index HTML missing PDF link: status=%s len=%d url=%s ban=%s",
            imslp_id,
            response.status_code,
            len(page_html),
            response.url,
            "ripping ban" in page_html.lower(),
        )
        raise ValueError(f"Could not resolve PDF URL for IMSLP {imslp_id}")

    pdf_url = html.unescape(match.group(1))
    if not pdf_url.lower().endswith(".pdf"):
        raise ValueError(f"Resolved URL is not a PDF for IMSLP {imslp_id}")
    return pdf_url, None


def _is_retryable_resolve_error(exc: BaseException) -> bool:
    if isinstance(exc, ValueError):
        return "Resolved URL is not a PDF" not in str(exc)
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (403, 429) or code >= 500
    return False


def resolve_imslp_pdf_url_with_retries(
    imslp_id: str,
    client: httpx.Client,
    *,
    max_attempts: int = IMSLP_RETRY_ATTEMPTS,
) -> tuple[str, bytes | None]:
    """Resolve an IMSLP edition PDF URL, retrying transient mirror/index failures."""
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return resolve_imslp_pdf_url(imslp_id, client)
        except Exception as exc:
            last_exc = exc
            if not _is_retryable_resolve_error(exc):
                raise
            if attempt + 1 >= max_attempts:
                break
            delay = IMSLP_RETRY_BASE_SECONDS * (3**attempt) + random.uniform(0, 1)
            logger.warning(
                "IMSLP %s resolve attempt %d/%d failed, retry in %.1fs: %s",
                imslp_id,
                attempt + 1,
                max_attempts,
                delay,
                exc,
            )
            time.sleep(delay)
    assert last_exc is not None
    logger.warning(
        "IMSLP %s resolve failed after %d attempts: %s",
        imslp_id,
        max_attempts,
        last_exc,
    )
    raise last_exc

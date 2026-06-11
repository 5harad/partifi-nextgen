"""Shared IMSLP / mirror PDF URL resolution and download helpers."""

from __future__ import annotations

import html
import re

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
PMLASIA_DISCLAIMER_COOKIE = "disclaimer_bypass"
PMLASIA_DISCLAIMER_VALUE = "OK"


def is_pdf_body(content: bytes, content_type: str = "") -> bool:
    if len(content) >= 4 and content[:4] == b"%PDF":
        return True
    return "application/pdf" in content_type.lower()


def mirror_request_cookies(url: str) -> dict[str, str]:
    """PML Asia (imslp.tw) requires a disclaimer cookie before serving PDF bytes."""
    if "imslp.tw" in url:
        return {PMLASIA_DISCLAIMER_COOKIE: PMLASIA_DISCLAIMER_VALUE}
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


def _fetch_pmlasia_pdf(
    client: httpx.Client, disclaimer_html: str, page_url: str
) -> tuple[str, bytes]:
    pdf_url = parse_pmlasia_pdf_url(disclaimer_html, page_url)
    if not pdf_url:
        raise ValueError(f"Could not parse PML Asia disclaimer page at {page_url}")

    response = client.get(pdf_url, cookies=mirror_request_cookies(pdf_url))
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if not is_pdf_body(response.content, content_type):
        raise ValueError(f"PML Asia mirror did not return a PDF at {pdf_url}")
    return str(response.url), response.content


def resolve_imslp_pdf_url(imslp_id: str, client: httpx.Client) -> tuple[str, bytes | None]:
    page_url = IMSLP_INDEX_URL.format(imslp_id=imslp_id)
    response = client.get(page_url)
    response.raise_for_status()

    direct = pdf_response_from_redirect(response)
    if direct:
        return direct

    if is_pmlasia_disclaimer(response.text):
        return _fetch_pmlasia_pdf(client, response.text, str(response.url))

    match = re.search(r'id="sm_dl_wait"\s+data-id="([^"]+)"', response.text)
    if not match:
        match = re.search(r'data-id="(https?://[^"]+\.pdf[^"]*)"', response.text, re.I)
    if not match:
        raise ValueError(f"Could not resolve PDF URL for IMSLP {imslp_id}")

    pdf_url = html.unescape(match.group(1))
    if not pdf_url.lower().endswith(".pdf"):
        raise ValueError(f"Resolved URL is not a PDF for IMSLP {imslp_id}")
    return pdf_url, None

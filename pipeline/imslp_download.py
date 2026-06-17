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

PMLASIA_PLACEHOLDER_RE = re.compile(
    r"PMLASIA(\d+)-placeholder-([^/?#]+\.pdf)",
    re.I,
)
PMLASIA_DOWNLOAD_URL = "https://imslp.tw/index.php?download=PMLASIA{pml_id}-{suffix}"

IMSLP_NO_DOWNLOAD_PDF_MSG = "No downloadable PDF is available for IMSLP {imslp_id}"


def rewrite_pmlasia_placeholder_url(url: str) -> str | None:
    """Map PML-CA placeholder stub URLs to the real PML-Asia download page."""
    match = PMLASIA_PLACEHOLDER_RE.search(url)
    if not match:
        return None
    pml_id, suffix = match.group(1), match.group(2)
    return PMLASIA_DOWNLOAD_URL.format(pml_id=pml_id, suffix=suffix)


def is_imslp_index_error_page(page_html: str, page_url: str = "") -> bool:
    """True when IMSLP's ImagefromIndex special page reports no downloadable file."""
    if "imagefromindex" not in page_url.lower():
        return False
    if re.search(r"<title>\s*Error\s*-\s*IMSLP\s*</title>", page_html, re.I):
        return True
    if re.search(
        r'<h1[^>]*id="firstHeading"[^>]*>\s*Error\s*</h1>',
        page_html,
        re.I,
    ):
        return True
    return False


def format_imslp_http_context(
    exc: BaseException,
    *,
    imslp_id: str | None = None,
    url: str | None = None,
    operation: str | None = None,
) -> str:
    """Build a single log line with IMSLP id, URL, host, and error details."""
    parts: list[str] = []
    if operation:
        parts.append(f"operation={operation}")
    if imslp_id:
        parts.append(f"imslp_id={imslp_id}")

    request_url = url
    if request_url is None and isinstance(exc, httpx.HTTPStatusError):
        request_url = str(exc.request.url)
        parts.append(f"status={exc.response.status_code}")
    elif request_url is None and isinstance(exc, httpx.RequestError) and exc.request is not None:
        request_url = str(exc.request.url)

    if request_url:
        parts.append(f"url={request_url}")
        host = httpx.URL(request_url).host
        if host:
            parts.append(f"host={host}")

    parts.append(f"error={type(exc).__name__}: {exc}")
    return " ".join(parts)


def log_imslp_http_failure(
    exc: BaseException,
    *,
    imslp_id: str | None = None,
    url: str | None = None,
    operation: str,
    level: int = logging.WARNING,
) -> None:
    logger.log(
        level,
        "IMSLP HTTP failure %s",
        format_imslp_http_context(
            exc,
            imslp_id=imslp_id,
            url=url,
            operation=operation,
        ),
    )


def is_pdf_body(content: bytes, content_type: str = "") -> bool:
    if len(content) >= 4 and content[:4] == b"%PDF":
        return True
    return "application/pdf" in content_type.lower()


def mirror_request_cookies(url: str) -> dict[str, str]:
    """PML mirror hosts require a disclaimer cookie before serving PDF bytes."""
    lowered = url.lower()
    if (
        "imslp.tw" in lowered
        or "petruccilibrary.us" in lowered
        or "petruccimusiclibrary.ca" in lowered
    ):
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
    if rewrite_pmlasia_placeholder_url(str(response.url)):
        return None
    return str(response.url), response.content


def is_pmlca_disclaimer(page_html: str, page_url: str = "") -> bool:
    if "petruccimusiclibrary.ca" in page_url.lower():
        return True
    return "Petrucci Music Library Canada" in page_html


def parse_pmlca_pdf_url(page_html: str, page_url: str) -> str | None:
    match = re.search(r'href="(/files/[^"]+\.pdf|files/[^"]+\.pdf)"', page_html, re.I)
    if not match:
        return None
    path = html.unescape(match.group(1))
    base = httpx.URL(page_url)
    if path.startswith("/"):
        return str(base.copy_with(path=path, query=None, fragment=None))
    return str(base.join(path))


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
    logger.info("IMSLP mirror PML-Asia disclaimer from=%s", page_url)
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
    logger.info("IMSLP mirror PML-US disclaimer from=%s", page_url)
    return _fetch_mirror_disclaimer_pdf(
        client,
        disclaimer_html,
        page_url,
        pdf_url=parse_pmlus_pdf_url(disclaimer_html, page_url),
        mirror_name="PML-US",
    )


def _fetch_pmlca_pdf(
    client: httpx.Client, disclaimer_html: str, page_url: str
) -> tuple[str, bytes]:
    logger.info("IMSLP mirror PML-CA disclaimer from=%s", page_url)
    return _fetch_mirror_disclaimer_pdf(
        client,
        disclaimer_html,
        page_url,
        pdf_url=parse_pmlca_pdf_url(disclaimer_html, page_url),
        mirror_name="PML-CA",
    )


def _follow_pmlca_disclaimer(
    client: httpx.Client, disclaimer_html: str, page_url: str
) -> tuple[str, bytes]:
    ca_url = parse_pmlca_pdf_url(disclaimer_html, page_url)
    if not ca_url:
        raise ValueError(f"Could not parse PML-CA disclaimer page at {page_url}")
    asia_url = rewrite_pmlasia_placeholder_url(ca_url)
    if asia_url:
        logger.info(
            "IMSLP mirror PML-CA placeholder redirect from=%s to=%s",
            page_url,
            asia_url,
        )
        return _fetch_pmlasia_via_placeholder(client, ca_url)
    return _fetch_pmlca_pdf(client, disclaimer_html, page_url)


def _fetch_pmlasia_via_placeholder(
    client: httpx.Client, placeholder_url: str
) -> tuple[str, bytes]:
    asia_url = rewrite_pmlasia_placeholder_url(placeholder_url)
    if not asia_url:
        raise ValueError(f"Not a PML-Asia placeholder URL: {placeholder_url}")
    logger.info(
        "IMSLP mirror PML-Asia placeholder from=%s to=%s",
        placeholder_url,
        asia_url,
    )

    response = client.get(asia_url, cookies=mirror_request_cookies(asia_url))
    response.raise_for_status()
    page_url = str(response.url)
    if is_pmlasia_disclaimer(response.text):
        return _fetch_pmlasia_pdf(client, response.text, page_url)

    direct = pdf_response_from_redirect(response)
    if direct:
        return direct

    raise ValueError(f"PML-Asia placeholder did not resolve at {asia_url}")


def fetch_mirror_pdf(client: httpx.Client, pdf_url: str) -> tuple[str, bytes]:
    """Download PDF bytes from a mirror URL, following disclaimer/placeholder chains."""
    if rewrite_pmlasia_placeholder_url(pdf_url):
        return _fetch_pmlasia_via_placeholder(client, pdf_url)

    response = client.get(pdf_url, cookies=mirror_request_cookies(pdf_url))
    response.raise_for_status()
    page_url = str(response.url)

    if is_pmlasia_disclaimer(response.text):
        return _fetch_pmlasia_pdf(client, response.text, page_url)
    if is_pmlus_disclaimer(response.text, page_url):
        return _fetch_pmlus_pdf(client, response.text, page_url)
    if is_pmlca_disclaimer(response.text, page_url):
        return _follow_pmlca_disclaimer(client, response.text, page_url)

    content_type = response.headers.get("content-type", "")
    if is_pdf_body(response.content, content_type):
        if rewrite_pmlasia_placeholder_url(page_url):
            return _fetch_pmlasia_via_placeholder(client, page_url)
        return page_url, response.content

    raise ValueError(f"Mirror did not return a PDF at {pdf_url}")


def resolve_imslp_pdf_url(imslp_id: str, client: httpx.Client) -> tuple[str, bytes | None]:
    page_url = IMSLP_INDEX_URL.format(imslp_id=imslp_id)
    response = client.get(page_url)
    response.raise_for_status()

    direct = pdf_response_from_redirect(response)
    if direct:
        return direct

    page_url = str(response.url)
    if is_imslp_index_error_page(response.text, page_url):
        raise ValueError(IMSLP_NO_DOWNLOAD_PDF_MSG.format(imslp_id=imslp_id))

    content_type = response.headers.get("content-type", "")
    if is_pdf_body(response.content, content_type) and rewrite_pmlasia_placeholder_url(page_url):
        return _fetch_pmlasia_via_placeholder(client, page_url)

    if is_pmlasia_disclaimer(response.text):
        return _fetch_pmlasia_pdf(client, response.text, page_url)

    if is_pmlus_disclaimer(response.text, page_url):
        return _fetch_pmlus_pdf(client, response.text, page_url)

    if is_pmlca_disclaimer(response.text, page_url):
        return _follow_pmlca_disclaimer(client, response.text, page_url)

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
    if rewrite_pmlasia_placeholder_url(pdf_url):
        return _fetch_pmlasia_via_placeholder(client, pdf_url)
    return pdf_url, None


def _is_retryable_resolve_error(exc: BaseException) -> bool:
    if isinstance(exc, ValueError):
        msg = str(exc)
        if "Resolved URL is not a PDF" in msg:
            return False
        if "No downloadable PDF is available" in msg:
            return False
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
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
                log_imslp_http_failure(
                    exc,
                    imslp_id=imslp_id,
                    operation="pdf_resolve",
                )
                raise
            if attempt + 1 >= max_attempts:
                break
            delay = IMSLP_RETRY_BASE_SECONDS * (3**attempt) + random.uniform(0, 1)
            log_imslp_http_failure(
                exc,
                imslp_id=imslp_id,
                operation=f"pdf_resolve attempt {attempt + 1}/{max_attempts}",
            )
            logger.warning(
                "IMSLP %s pdf_resolve retry in %.1fs",
                imslp_id,
                delay,
            )
            time.sleep(delay)
    assert last_exc is not None
    log_imslp_http_failure(
        last_exc,
        imslp_id=imslp_id,
        operation=f"pdf_resolve failed after {max_attempts} attempts",
        level=logging.ERROR,
    )
    raise last_exc

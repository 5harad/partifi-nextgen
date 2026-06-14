"""IMSLP metadata lookup (cache + scrape)."""

from __future__ import annotations

import html
import logging
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.tables import ImslpInfo
from pipeline.imslp_download import log_imslp_http_failure

logger = logging.getLogger(__name__)

IMSLP_BASE = "https://imslp.org"
REVERSE_LOOKUP_URL = (
    IMSLP_BASE
    + "/index.php?title=Special:ReverseLookup&action=submit&indexsearch={imslp_id}"
)
IMSLP_ID_RX = re.compile(r"IMSLP(\d+)", re.I)
IMSLP_HEADERS = {
    "User-Agent": "Partifi/1.0 (+https://partifi.org)",
}
REQUEST_TIMEOUT = 15.0

IMSLP_ERROR_NOT_FOUND = "Edition not found."
IMSLP_ERROR_NOT_PDF = "Not a PDF score."


class ImslpLookupError(ValueError):
    def __init__(self, message: str, *, not_pdf: bool = False) -> None:
        super().__init__(message)
        self.not_pdf = not_pdf


def _fail_lookup(row: ImslpInfo | None) -> None:
    if row and row.file_type and row.file_type.upper() != "PDF":
        raise ImslpLookupError(IMSLP_ERROR_NOT_PDF, not_pdf=True)
    raise ImslpLookupError(IMSLP_ERROR_NOT_FOUND)


def normalize_imslp_id(raw: str) -> str | None:
    text = raw.strip().lstrip("#")
    if text.isdigit():
        return text
    match = IMSLP_ID_RX.search(raw)
    return match.group(1) if match else None


def _normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.encode("ascii", "ignore").decode("ascii")


def _abs_imslp_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return IMSLP_BASE + url
    return url


def _edition_snippet(page_html: str, imslp_id: str) -> str:
    marker = f">#{imslp_id}<"
    idx = page_html.find(marker)
    if idx < 0:
        return page_html[:12000]
    return page_html[max(0, idx - 100) : idx + 8000]


def parse_imslp_page_html(page_html: str, imslp_id: str) -> dict[str, str]:
    title = ""
    composer = ""
    title_match = re.search(r"<title>(.*?)\s*\((.*?)\).*?</title>", page_html, re.S | re.I)
    if title_match:
        title = _normalize_text(title_match.group(1))
        composer_raw = _normalize_text(title_match.group(2))
        names = composer_raw.split(", ", 1)
        composer = names[0] if len(names) == 1 else f"{names[1]} {names[0]}"

    snippet = _edition_snippet(page_html, imslp_id)

    publisher = ""
    pub_match = re.search(
        r"Publisher Info.:.*?<p class=\"we_edition_entry\">(.*?)</p>",
        snippet,
        re.S | re.I,
    )
    if pub_match:
        pub_info = re.sub(r"<br\s*/?>", ", ", pub_match.group(1))
        publisher = _normalize_text(re.sub(r"<[^>]+>", "", pub_info))

    copyright_raw = ""
    copy_match = re.search(
        r"Copyright:.*?<p class=\"we_edition_entry\">(.*?)</p>",
        snippet,
        re.S | re.I,
    )
    if copy_match:
        copyright_text = re.sub(r"<br\s*/?>", ", ", copy_match.group(1))
        copyright_text = re.sub(r"<[^>]+>", "", copyright_text)
        copyright_text = re.sub(r"\[.*?\]", "", copyright_text)
        copyright_raw = _normalize_text(copyright_text)

    file_type = ""
    type_match = re.search(
        r"<a href=\"/wiki/IMSLP:File_formats\" title=\"IMSLP:File formats\">(.*?)</a>",
        snippet,
        re.S | re.I,
    )
    if type_match:
        file_type = _normalize_text(re.sub(r"<[^>]+>", "", type_match.group(1)))

    return {
        "title": title,
        "composer": composer,
        "publisher": publisher,
        "copyright_raw": copyright_raw,
        "file_type": file_type,
    }


def parse_reverse_lookup_location(location: str) -> tuple[str, str] | None:
    id_match = re.search(r"#IMSLP(\d+)", location, re.I)
    if not id_match:
        return None
    page_url = _abs_imslp_url(location.split("#")[0])
    return page_url, id_match.group(1)


def _fetch_imslp_page(client: httpx.Client, imslp_id: str) -> tuple[str, str] | None:
    reverse_url = REVERSE_LOOKUP_URL.format(imslp_id=imslp_id)
    resp = client.get(reverse_url, follow_redirects=False)
    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("location", "")
        parsed = parse_reverse_lookup_location(location)
        if not parsed or parsed[1] != imslp_id:
            return None
        page_url, _ = parsed
        page_resp = client.get(page_url, follow_redirects=True)
        page_resp.raise_for_status()
        return page_resp.text, location
    if resp.status_code == 200 and resp.text:
        return resp.text, reverse_url
    return None


def lookup_imslp_info_remote(raw_id: str) -> dict[str, str]:
    """Thread-safe lookup using a fresh DB session (for async API handlers)."""
    from app.db import SessionLocal

    imslp_id = normalize_imslp_id(raw_id) or raw_id.strip()
    db = SessionLocal()
    try:
        return lookup_imslp_info(db, raw_id)
    except httpx.TimeoutException as exc:
        log_imslp_http_failure(
            exc,
            imslp_id=imslp_id,
            operation="metadata_lookup",
        )
        raise TimeoutError("IMSLP lookup timed out") from exc
    except httpx.HTTPError as exc:
        log_imslp_http_failure(
            exc,
            imslp_id=imslp_id,
            operation="metadata_lookup",
            level=logging.ERROR,
        )
        raise
    finally:
        db.close()


def _cache_row_complete(row: ImslpInfo) -> bool:
    return bool(row.title and row.composer and row.file_type)


def _row_to_result(row: ImslpInfo) -> dict[str, str] | None:
    if row.file_type and row.file_type.upper() != "PDF":
        return None
    return {
        "imslp_id": row.id,
        "title": row.title or "",
        "composer": row.composer or "",
        "publisher": row.publisher or "",
        "copyright_raw": row.copyright or "",
        "file_type": row.file_type or "",
    }


def _upsert_cache(db: Session, imslp_id: str, data: dict[str, str], imslp_url: str) -> None:
    row = db.get(ImslpInfo, imslp_id)
    if row is None:
        row = ImslpInfo(id=imslp_id)
        db.add(row)
    row.title = data.get("title") or row.title
    row.composer = data.get("composer") or row.composer
    row.publisher = data.get("publisher") or row.publisher
    row.copyright = data.get("copyright_raw") or row.copyright
    row.url = imslp_url or row.url
    row.file_type = data.get("file_type") or row.file_type
    db.commit()


def lookup_imslp_info(db: Session, raw_id: str, *, client: httpx.Client | None = None) -> dict[str, str]:
    imslp_id = normalize_imslp_id(raw_id)
    if not imslp_id:
        _fail_lookup(None)

    row = db.get(ImslpInfo, imslp_id)
    if row and _cache_row_complete(row):
        result = _row_to_result(row)
        if result:
            return result
        _fail_lookup(row)

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=REQUEST_TIMEOUT, headers=IMSLP_HEADERS)

    try:
        assert client is not None
        fetched = _fetch_imslp_page(client, imslp_id)
        if not fetched:
            if row:
                result = _row_to_result(row)
                if result:
                    return result
            _fail_lookup(row)

        page_html, imslp_url = fetched
        parsed = parse_imslp_page_html(page_html, imslp_id)
        if not parsed.get("title") and not parsed.get("composer"):
            if row:
                result = _row_to_result(row)
                if result:
                    return result
            _fail_lookup(row)

        _upsert_cache(db, imslp_id, parsed, imslp_url)
        row = db.get(ImslpInfo, imslp_id)
        if row:
            result = _row_to_result(row)
            if result:
                return result
        _fail_lookup(row)
    finally:
        if owns_client:
            client.close()

    raise AssertionError("unreachable")


def lookup_imslp_info_for_api(db: Session, raw_id: str) -> dict[str, Any]:
    return lookup_imslp_info(db, raw_id)

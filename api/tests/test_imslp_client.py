"""Tests for workers/imslp_client.py (IMSLP PDF resolution)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKERS_ROOT = REPO_ROOT / "workers"
for root in (str(REPO_ROOT), str(WORKERS_ROOT)):
    if root not in sys.path:
        sys.path.insert(0, root)

from imslp_client import download_imslp_pdf, download_imslp_pdf_url  # noqa: E402
from pipeline.imslp_download import resolve_imslp_pdf_url  # noqa: E402


def _mock_response(
    *,
    url: str,
    text: str = "",
    content: bytes = b"",
    content_type: str = "text/html",
) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(
        200,
        request=request,
        headers={"content-type": content_type},
        content=content or text.encode(),
        text=text if text else None,
    )


def test_resolve_pdf_url_when_redirect_lands_on_pdf() -> None:
    pdf_url = (
        "https://ks15.imslp.org/files/imglnks/usimg/0/0a/"
        "IMSLP930226-PMLP1460139-Bax_-_Aspiration.pdf"
    )
    pdf_bytes = b"%PDF-1.4 fake pdf body"
    client = MagicMock()
    client.get.return_value = _mock_response(url=pdf_url, content=pdf_bytes, content_type="application/pdf")

    url, cached = resolve_imslp_pdf_url("930226", client)

    assert url == pdf_url
    assert cached == pdf_bytes
    client.get.assert_called_once()


def test_resolve_pdf_url_from_html_data_id() -> None:
    html = (
        '<div id="sm_dl_wait" data-id="https://vmirror.imslp.org/files/foo.pdf"></div>'
    )
    client = MagicMock()
    client.get.return_value = _mock_response(
        url="https://imslp.org/wiki/Special:ImagefromIndex/930226",
        text=html,
    )

    url, cached = resolve_imslp_pdf_url("930226", client)

    assert url == "https://vmirror.imslp.org/files/foo.pdf"
    assert cached is None


def test_download_imslp_pdf_uses_presolved_url(tmp_path: Path) -> None:
    pdf_url = "https://vmirror.imslp.org/files/foo.pdf"
    pdf_bytes = b"%PDF-1.4 fake pdf body"
    dest = tmp_path / "score.pdf"

    client = MagicMock()
    stream_response = MagicMock()
    stream_response.raise_for_status = MagicMock()
    stream_response.headers = {"content-length": str(len(pdf_bytes))}
    stream_response.iter_bytes = MagicMock(return_value=[pdf_bytes])
    stream_context = MagicMock()
    stream_context.__enter__ = MagicMock(return_value=stream_response)
    stream_context.__exit__ = MagicMock(return_value=False)
    client.stream.return_value = stream_context

    size = download_imslp_pdf_url(pdf_url, dest, client)

    assert size == len(pdf_bytes)
    assert dest.read_bytes() == pdf_bytes
    client.stream.assert_called_once()
    client.get.assert_not_called()

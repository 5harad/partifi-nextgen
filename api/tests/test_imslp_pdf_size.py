from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.score_limits import ScoreTooLargeError
from app.services.imslp_pdf import check_imslp_pdf_size, resolve_imslp_pdf_url


def _mock_response(
    *,
    url: str,
    text: str = "",
    content: bytes = b"",
    content_type: str = "text/html",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(
        200,
        request=request,
        headers={"content-type": content_type, **(headers or {})},
        content=content or text.encode(),
        text=text if text else None,
    )


def test_check_imslp_pdf_size_rejects_large_content_length() -> None:
    html = '<div id="sm_dl_wait" data-id="https://vmirror.imslp.org/files/foo.pdf"></div>'
    client = MagicMock()
    client.get.return_value = _mock_response(
        url="https://imslp.org/wiki/Special:ImagefromIndex/696200",
        text=html,
    )
    client.head.return_value = _mock_response(
        url="https://vmirror.imslp.org/files/foo.pdf",
        headers={"content-length": "188392869"},
    )

    with pytest.raises(ScoreTooLargeError, match="188 MB"):
        check_imslp_pdf_size("696200", client=client)


def test_check_imslp_pdf_size_allows_small_direct_pdf() -> None:
    pdf_url = "https://ks15.imslp.org/files/foo.pdf"
    pdf_bytes = b"%PDF-1.4" + b"x" * 1000
    client = MagicMock()
    client.get.return_value = _mock_response(
        url=pdf_url,
        content=pdf_bytes,
        content_type="application/pdf",
    )

    check_imslp_pdf_size("818713", client=client)
    client.head.assert_not_called()


def test_resolve_imslp_pdf_url_from_html() -> None:
    html = '<div id="sm_dl_wait" data-id="https://vmirror.imslp.org/files/foo.pdf"></div>'
    client = MagicMock()
    client.get.return_value = _mock_response(
        url="https://imslp.org/wiki/Special:ImagefromIndex/930226",
        text=html,
    )

    url, cached = resolve_imslp_pdf_url("930226", client)

    assert url == "https://vmirror.imslp.org/files/foo.pdf"
    assert cached is None

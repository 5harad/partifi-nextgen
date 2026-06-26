from unittest.mock import MagicMock, patch

import httpx
import pytest

from pipeline.imslp_download import (
    format_imslp_http_context,
    fetch_mirror_pdf,
    is_imslp_index_error_page,
    is_pdf_body,
    is_pmlasia_disclaimer,
    is_pmlca_disclaimer,
    is_pmleu_disclaimer,
    is_pmlus_disclaimer,
    mirror_request_cookies,
    parse_pmlasia_pdf_url,
    parse_pmlca_pdf_url,
    parse_pmleu_pdf_url,
    parse_pmlus_pdf_url,
    pdf_response_from_redirect,
    resolve_imslp_pdf_url,
    resolve_imslp_pdf_url_with_retries,
    rewrite_pmlasia_placeholder_url,
)

PMLCA_DIRECT_HTML = """<!doctype html>
<html><head><title>Petrucci Music Library Canada</title></head>
<body>
<a onclick="setC('disclaimer_bypass','OK',365)"
 href="/files/imglnks/caimg/1/12/IMSLP1234567-real-score.pdf"
 class="bigbutton">I understand, continue</a>
</body></html>
"""

PMLCA_DIRECT_URL = (
    "https://petruccimusiclibrary.ca/files/imglnks/caimg/1/12/IMSLP1234567-real-score.pdf"
)

IMSLP_INDEX_ERROR_HTML = """<!doctype html>
<html><head><title>Error - IMSLP</title></head>
<body><h1 id="firstHeading" class="firstHeading pagetitle page-header">
Error</h1></body></html>
"""

PMLCA_HTML = """<!doctype html>
<html><head><title>Petrucci Music Library Canada</title></head>
<body>
<a onclick="setC('disclaimer_bypass','OK',365)"
 href="/files/imglnks/caimg/9/91/IMSLP1009967-PMLP1573253-PMLASIA00851-placeholder-shostakovich_cwmg_v5-2.pdf"
 class="bigbutton">I understand, continue</a>
</body></html>
"""

PLACEHOLDER_URL = (
    "https://petruccimusiclibrary.ca/files/imglnks/caimg/9/91/"
    "IMSLP1009967-PMLP1573253-PMLASIA00851-placeholder-shostakovich_cwmg_v5-2.pdf"
)
PMLASIA_DOWNLOAD_URL = (
    "https://imslp.tw/index.php?download=PMLASIA00851-shostakovich_cwmg_v5-2.pdf"
)
PMLASIA_UPLOAD_URL = "https://imslp.tw/uploads/PMLASIA00851-shostakovich_cwmg_v5-2.pdf"

PMLASIA_HTML = """<!doctype html>
<html><head><script>
const PMLASIA_DOWNLOAD_TARGET = "uploads\\/PMLASIA00854-shostakovich_cwmg_v8-2.pdf";
</script></head>
<body><a href="uploads/PMLASIA00854-shostakovich_cwmg_v8-2.pdf">continue</a></body></html>
"""

PMLUS_HTML = """<!doctype html>
<html><head><title>Petrucci Music Library US</title></head>
<body>
<a onclick="setC('disclaimer_bypass','OK',365)"
 href="files/imglnks/music_files/PMLUS00101-debussypetitesuitescore_II.Cortege.pdf"
 class="bigbutton">I understand, continue</a>
</body></html>
"""

PMLEU_HTML = """<!doctype html>
<html><head><title>IMSLP-EU</title></head>
<body>
<a onclick="setC('disclaimer_bypass','OK',365)"
 href="/files/imglnks/euimg/c/ce/IMSLP903211-PMLP8846-HenleBeethovenWerke_Abteilung5Band1_Op_12_1.pdf"
 class="bigbutton">I understand, continue</a>
</body></html>
"""


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


def test_is_pdf_body() -> None:
    assert is_pdf_body(b"%PDF-1.4", "text/html")
    assert not is_pdf_body(b"<html>", "text/html")
    assert is_pdf_body(b"xxxx", "application/pdf")


def test_format_imslp_http_context_connect_error() -> None:
    url = "https://petruccilibrary.us/files/foo.pdf"
    request = httpx.Request("GET", url)
    exc = httpx.ConnectError("[Errno 111] Connection refused", request=request)
    context = format_imslp_http_context(
        exc,
        imslp_id="33421",
        operation="metadata_lookup",
    )
    assert "operation=metadata_lookup" in context
    assert "imslp_id=33421" in context
    assert f"url={url}" in context
    assert "host=petruccilibrary.us" in context
    assert "ConnectError" in context


def test_format_imslp_http_context_http_status_error() -> None:
    url = "https://imslp.org/wiki/Special:ImagefromIndex/33421"
    request = httpx.Request("GET", url)
    response = httpx.Response(429, request=request)
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
    context = format_imslp_http_context(exc, imslp_id="33421", operation="pdf_resolve")
    assert "status=429" in context
    assert "host=imslp.org" in context


def test_pdf_response_rejects_html_url_ending_in_pdf() -> None:
    url = "https://imslp.tw/index.php?download=foo.pdf"
    response = _mock_response(url=url, text=PMLASIA_HTML, content_type="text/html")
    assert pdf_response_from_redirect(response) is None


def test_pdf_response_rejects_placeholder_ticket_pdf() -> None:
    response = _mock_response(
        url=PLACEHOLDER_URL,
        content=b"%PDF-1.4 placeholder ticket",
        content_type="application/pdf",
    )
    assert pdf_response_from_redirect(response) is None


def test_rewrite_pmlasia_placeholder_url() -> None:
    assert rewrite_pmlasia_placeholder_url(PLACEHOLDER_URL) == PMLASIA_DOWNLOAD_URL
    linkhandler = (
        "https://petruccimusiclibrary.ca/linkhandler.php?path=/imglnks/caimg/9/91/"
        "IMSLP1009967-PMLP1573253-PMLASIA00851-placeholder-shostakovich_cwmg_v5-2.pdf"
    )
    assert rewrite_pmlasia_placeholder_url(linkhandler) == PMLASIA_DOWNLOAD_URL
    assert rewrite_pmlasia_placeholder_url("https://vmirror.imslp.org/files/foo.pdf") is None


def test_parse_pmlca_pdf_url() -> None:
    page_url = "https://petruccimusiclibrary.ca/linkhandler.php?path=ignored"
    assert parse_pmlca_pdf_url(PMLCA_HTML, page_url) == PLACEHOLDER_URL
    assert is_pmlca_disclaimer(PMLCA_HTML, page_url)


def test_parse_pmlasia_pdf_url() -> None:
    page_url = "https://imslp.tw/index.php?download=foo.pdf"
    assert parse_pmlasia_pdf_url(PMLASIA_HTML, page_url) == (
        "https://imslp.tw/uploads/PMLASIA00854-shostakovich_cwmg_v8-2.pdf"
    )


def test_mirror_request_cookies_for_imslp_tw() -> None:
    assert mirror_request_cookies("https://imslp.tw/uploads/foo.pdf") == {
        "disclaimer_bypass": "OK"
    }
    assert mirror_request_cookies("https://www.petruccilibrary.us/files/foo.pdf") == {
        "disclaimer_bypass": "OK"
    }
    assert mirror_request_cookies("https://petruccimusiclibrary.ca/files/foo.pdf") == {
        "disclaimer_bypass": "OK"
    }
    assert mirror_request_cookies("https://imslp.eu/files/foo.pdf") == {
        "disclaimer_bypass": "OK"
    }
    assert mirror_request_cookies("https://vmirror.imslp.org/files/foo.pdf") == {}


def test_is_imslp_index_error_page() -> None:
    page_url = "https://imslp.org/wiki/Special:ImagefromIndex/74685"
    assert is_imslp_index_error_page(IMSLP_INDEX_ERROR_HTML, page_url)
    assert not is_imslp_index_error_page(PMLASIA_HTML, "https://imslp.tw/index.php?download=foo.pdf")


def test_resolve_imslp_index_error_fails_without_retry() -> None:
    page_url = "https://imslp.org/wiki/Special:ImagefromIndex/74685"
    client = MagicMock()
    client.get.return_value = _mock_response(url=page_url, text=IMSLP_INDEX_ERROR_HTML)

    with pytest.raises(ValueError, match="No downloadable PDF is available"):
        resolve_imslp_pdf_url("74685", client)

    assert client.get.call_count == 1


def test_resolve_imslp_index_error_not_retried() -> None:
    page_url = "https://imslp.org/wiki/Special:ImagefromIndex/74685"
    client = MagicMock()
    client.get.return_value = _mock_response(url=page_url, text=IMSLP_INDEX_ERROR_HTML)

    with patch("pipeline.imslp_download.time.sleep") as sleep_mock:
        with pytest.raises(ValueError, match="No downloadable PDF is available"):
            resolve_imslp_pdf_url_with_retries("74685", client, max_attempts=3)

    assert client.get.call_count == 1
    sleep_mock.assert_not_called()


def test_fetch_mirror_pdf_content_length_mismatch() -> None:
    pdf_url = "https://imslp.tw/uploads/foo.pdf"
    pdf_bytes = b"%PDF-1.7 real score"
    client = MagicMock()
    client.get.return_value = _mock_response(
        url=pdf_url,
        content=pdf_bytes,
        content_type="application/pdf",
        headers={"content-length": str(len(pdf_bytes) + 100)},
    )

    with pytest.raises(ValueError, match="Download incomplete"):
        fetch_mirror_pdf(client, pdf_url)


def test_fetch_mirror_pdf_follows_asia_disclaimer() -> None:
    disclaimer_url = "https://imslp.tw/index.php?download=PMLASIA00854-shostakovich_cwmg_v8-2.pdf"
    pdf_url = "https://imslp.tw/uploads/PMLASIA00854-shostakovich_cwmg_v8-2.pdf"
    pdf_bytes = b"%PDF-1.7 real score"

    client = MagicMock()
    client.get.side_effect = [
        _mock_response(url=disclaimer_url, text=PMLASIA_HTML),
        _mock_response(url=pdf_url, content=pdf_bytes, content_type="application/pdf"),
    ]

    url, cached = fetch_mirror_pdf(client, disclaimer_url)

    assert url == pdf_url
    assert cached == pdf_bytes
    assert client.get.call_count == 2


def test_resolve_pmlca_direct_disclaimer_fetches_pdf_with_cookie() -> None:
    page_url = "https://petruccimusiclibrary.ca/linkhandler.php?path=ignored"
    pdf_bytes = b"%PDF-1.7 real score"

    client = MagicMock()
    client.get.side_effect = [
        _mock_response(url=page_url, text=PMLCA_DIRECT_HTML),
        _mock_response(url=PMLCA_DIRECT_URL, content=pdf_bytes, content_type="application/pdf"),
    ]

    url, cached = resolve_imslp_pdf_url("1234567", client)

    assert url == PMLCA_DIRECT_URL
    assert cached == pdf_bytes
    assert client.get.call_count == 2
    assert client.get.call_args_list[1].kwargs["cookies"] == {"disclaimer_bypass": "OK"}


def test_parse_pmlus_pdf_url() -> None:
    page_url = (
        "https://www.petruccilibrary.us/linkhandler.php?"
        "path=files/imglnks/music_files/PMLUS00101-debussypetitesuitescore_II.Cortege.pdf"
    )
    assert parse_pmlus_pdf_url(PMLUS_HTML, page_url) == (
        "https://www.petruccilibrary.us/files/imglnks/music_files/"
        "PMLUS00101-debussypetitesuitescore_II.Cortege.pdf"
    )
    assert is_pmlus_disclaimer(PMLUS_HTML, page_url)


def test_resolve_pmlasia_disclaimer_fetches_pdf_with_cookie() -> None:
    disclaimer_url = "https://imslp.tw/index.php?download=PMLASIA00854-shostakovich_cwmg_v8-2.pdf"
    pdf_url = "https://imslp.tw/uploads/PMLASIA00854-shostakovich_cwmg_v8-2.pdf"
    pdf_bytes = b"%PDF-1.7 test"

    client = MagicMock()
    client.get.side_effect = [
        _mock_response(url=disclaimer_url, text=PMLASIA_HTML),
        _mock_response(url=pdf_url, content=pdf_bytes, content_type="application/pdf"),
    ]

    url, cached = resolve_imslp_pdf_url("1009976", client)

    assert url == pdf_url
    assert cached == pdf_bytes
    assert client.get.call_count == 2
    assert client.get.call_args_list[1].kwargs["cookies"] == {"disclaimer_bypass": "OK"}
    assert is_pmlasia_disclaimer(PMLASIA_HTML)


def test_resolve_with_retries_succeeds_on_second_attempt() -> None:
    html = '<div id="sm_dl_wait" data-id="https://vmirror.imslp.org/files/foo.pdf"></div>'
    client = MagicMock()
    client.get.side_effect = [
        _mock_response(
            url="https://imslp.org/wiki/Special:ImagefromIndex/930226",
            text="<html>no pdf markers</html>",
        ),
        _mock_response(
            url="https://imslp.org/wiki/Special:ImagefromIndex/930226",
            text=html,
        ),
    ]

    with patch("pipeline.imslp_download.time.sleep"):
        url, cached = resolve_imslp_pdf_url_with_retries("930226", client, max_attempts=2)

    assert url == "https://vmirror.imslp.org/files/foo.pdf"
    assert cached is None
    assert client.get.call_count == 2


def test_resolve_pmlca_placeholder_fetches_real_pdf_via_asia() -> None:
    pdf_bytes = b"%PDF-1.7 real score"

    client = MagicMock()
    client.get.side_effect = [
        _mock_response(
            url="https://petruccimusiclibrary.ca/linkhandler.php?path=ignored",
            text=PMLCA_HTML,
        ),
        _mock_response(url=PMLASIA_DOWNLOAD_URL, text=PMLASIA_HTML),
        _mock_response(url=PMLASIA_UPLOAD_URL, content=pdf_bytes, content_type="application/pdf"),
    ]

    url, cached = resolve_imslp_pdf_url("1009967", client)

    assert url == PMLASIA_UPLOAD_URL
    assert cached == pdf_bytes
    assert client.get.call_count == 3
    assert client.get.call_args_list[1].kwargs["cookies"] == {"disclaimer_bypass": "OK"}


def test_resolve_sm_dl_wait_placeholder_fetches_real_pdf_via_asia() -> None:
    html = (
        '<div id="sm_dl_wait" data-id="'
        f"{PLACEHOLDER_URL}"
        '"></div>'
    )
    pdf_bytes = b"%PDF-1.7 real score"

    client = MagicMock()
    client.get.side_effect = [
        _mock_response(
            url="https://imslp.org/wiki/Special:ImagefromIndex/1009967",
            text=html,
        ),
        _mock_response(url=PMLASIA_DOWNLOAD_URL, text=PMLASIA_HTML),
        _mock_response(url=PMLASIA_UPLOAD_URL, content=pdf_bytes, content_type="application/pdf"),
    ]

    url, cached = resolve_imslp_pdf_url("1009967", client)

    assert url == PMLASIA_UPLOAD_URL
    assert cached == pdf_bytes
    assert client.get.call_count == 3


def test_resolve_pmlus_disclaimer_fetches_pdf_with_cookie() -> None:
    disclaimer_url = (
        "https://www.petruccilibrary.us/linkhandler.php?"
        "path=files/imglnks/music_files/PMLUS00101-debussypetitesuitescore_II.Cortege.pdf"
    )
    pdf_url = (
        "https://www.petruccilibrary.us/files/imglnks/music_files/"
        "PMLUS00101-debussypetitesuitescore_II.Cortege.pdf"
    )
    pdf_bytes = b"%PDF-1.7 test"

    client = MagicMock()
    client.get.side_effect = [
        _mock_response(url=disclaimer_url, text=PMLUS_HTML),
        _mock_response(url=pdf_url, content=pdf_bytes, content_type="application/pdf"),
    ]

    url, cached = resolve_imslp_pdf_url("398248", client)

    assert url == pdf_url
    assert cached == pdf_bytes
    assert client.get.call_count == 2
    assert client.get.call_args_list[1].kwargs["cookies"] == {"disclaimer_bypass": "OK"}


def test_parse_pmleu_pdf_url() -> None:
    page_url = (
        "https://imslp.eu/linkhandler.php?"
        "path=/imglnks/euimg/c/ce/IMSLP903211-PMLP8846-HenleBeethovenWerke_Abteilung5Band1_Op_12_1.pdf"
    )
    pdf_url = (
        "https://imslp.eu/files/imglnks/euimg/c/ce/"
        "IMSLP903211-PMLP8846-HenleBeethovenWerke_Abteilung5Band1_Op_12_1.pdf"
    )
    assert parse_pmleu_pdf_url(PMLEU_HTML, page_url) == pdf_url
    assert is_pmleu_disclaimer(PMLEU_HTML, page_url)


def test_resolve_pmleu_disclaimer_fetches_pdf_with_cookie() -> None:
    disclaimer_url = (
        "https://imslp.eu/linkhandler.php?"
        "path=/imglnks/euimg/c/ce/IMSLP903211-PMLP8846-HenleBeethovenWerke_Abteilung5Band1_Op_12_1.pdf"
    )
    pdf_url = (
        "https://imslp.eu/files/imglnks/euimg/c/ce/"
        "IMSLP903211-PMLP8846-HenleBeethovenWerke_Abteilung5Band1_Op_12_1.pdf"
    )
    pdf_bytes = b"%PDF-1.6 test"

    client = MagicMock()
    client.get.side_effect = [
        _mock_response(url=disclaimer_url, text=PMLEU_HTML),
        _mock_response(url=pdf_url, content=pdf_bytes, content_type="application/pdf"),
    ]

    url, cached = resolve_imslp_pdf_url("903211", client)

    assert url == pdf_url
    assert cached == pdf_bytes
    assert client.get.call_count == 2
    assert client.get.call_args_list[1].kwargs["cookies"] == {"disclaimer_bypass": "OK"}

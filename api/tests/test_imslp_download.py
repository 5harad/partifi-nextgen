from unittest.mock import MagicMock, patch

import httpx

from pipeline.imslp_download import (
    format_imslp_http_context,
    is_pdf_body,
    is_pmlasia_disclaimer,
    is_pmlus_disclaimer,
    mirror_request_cookies,
    parse_pmlasia_pdf_url,
    parse_pmlus_pdf_url,
    pdf_response_from_redirect,
    resolve_imslp_pdf_url,
    resolve_imslp_pdf_url_with_retries,
)

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
    assert mirror_request_cookies("https://vmirror.imslp.org/files/foo.pdf") == {}


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

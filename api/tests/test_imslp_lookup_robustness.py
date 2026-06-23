import threading
from unittest.mock import MagicMock

import httpx
import pytest

from app.services.imslp import (
    ImslpLookupCancelled,
    _check_cancelled,
    _fetch_imslp_page,
)
from pipeline.imslp_download import _is_retryable_resolve_error


def test_check_cancelled_raises() -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ImslpLookupCancelled):
        _check_cancelled(cancel)


def test_fetch_imslp_page_honours_cancel_before_second_request() -> None:
    reverse_response = httpx.Response(
        302,
        headers={"location": "//imslp.org/wiki/File:Example.pdf#IMSLP123"},
        request=httpx.Request(
            "GET",
            "https://imslp.org/index.php?title=Special:ReverseLookup&action=submit&indexsearch=123",
        ),
    )
    client = MagicMock()
    cancel = threading.Event()

    def get_side_effect(*args, **kwargs):
        cancel.set()
        return reverse_response

    client.get.side_effect = get_side_effect

    with pytest.raises(ImslpLookupCancelled):
        _fetch_imslp_page(client, "123", cancel=cancel)

    assert client.get.call_count == 1


def test_fetch_imslp_page_uses_first_disambiguation_result() -> None:
    reverse_html = """
    <a href="/wiki/6_Flute_Sonatas,_Op.19_(Boismortier,_Joseph_Bodin_de)#IMSLP396942">A</a>
    <a href="/wiki/Flute_Sonata_in_G_major,_PB_325_(Boismortier,_Joseph_Bodin_de)#IMSLP396942">B</a>
    """
    work_html = "<html><head><title>Sonata (Composer, Name)</title></head><body>#IMSLP396942</body></html>"
    reverse_response = httpx.Response(
        200,
        text=reverse_html,
        request=httpx.Request(
            "GET",
            "https://imslp.org/index.php?title=Special:ReverseLookup&action=submit&indexsearch=396942",
        ),
    )
    work_response = httpx.Response(
        200,
        text=work_html,
        request=httpx.Request(
            "GET",
            "https://imslp.org/wiki/6_Flute_Sonatas,_Op.19_(Boismortier,_Joseph_Bodin_de)",
        ),
    )
    client = MagicMock()
    client.get.side_effect = [reverse_response, work_response]

    page_html, imslp_url = _fetch_imslp_page(client, "396942")

    assert "Sonata (Composer, Name)" in page_html
    assert imslp_url.endswith("#IMSLP396942")
    assert client.get.call_count == 2
    assert "6_Flute_Sonatas" in str(client.get.call_args_list[1][0][0])


def test_connect_error_is_retryable_for_pdf_resolve() -> None:
    request = httpx.Request("GET", "https://petruccilibrary.us/files/foo.pdf")
    exc = httpx.ConnectError("[Errno 111] Connection refused", request=request)
    assert _is_retryable_resolve_error(exc) is True


def test_connect_error_is_not_retryable_for_non_pdf_value_error() -> None:
    assert _is_retryable_resolve_error(ValueError("Resolved URL is not a PDF for IMSLP 1")) is False


def test_no_downloadable_pdf_is_not_retryable() -> None:
    assert (
        _is_retryable_resolve_error(
            ValueError("No downloadable PDF is available for IMSLP 74685")
        )
        is False
    )

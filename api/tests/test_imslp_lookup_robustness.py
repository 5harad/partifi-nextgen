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


def test_connect_error_is_retryable_for_pdf_resolve() -> None:
    request = httpx.Request("GET", "https://petruccilibrary.us/files/foo.pdf")
    exc = httpx.ConnectError("[Errno 111] Connection refused", request=request)
    assert _is_retryable_resolve_error(exc) is True


def test_connect_error_is_not_retryable_for_non_pdf_value_error() -> None:
    assert _is_retryable_resolve_error(ValueError("Resolved URL is not a PDF for IMSLP 1")) is False

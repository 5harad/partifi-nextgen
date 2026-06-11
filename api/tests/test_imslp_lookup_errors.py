import pytest

from app.models.tables import ImslpInfo
from app.services.imslp import (
    IMSLP_ERROR_NOT_FOUND,
    IMSLP_ERROR_NOT_PDF,
    ImslpLookupError,
    _fail_lookup,
)


def test_fail_lookup_not_found() -> None:
    with pytest.raises(ImslpLookupError, match=IMSLP_ERROR_NOT_FOUND) as exc:
        _fail_lookup(None)
    assert exc.value.not_pdf is False


def test_fail_lookup_not_pdf() -> None:
    row = ImslpInfo(id="123", file_type="MIDI")
    with pytest.raises(ImslpLookupError, match=IMSLP_ERROR_NOT_PDF) as exc:
        _fail_lookup(row)
    assert exc.value.not_pdf is True

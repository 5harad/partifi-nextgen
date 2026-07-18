from pathlib import Path

import pytest

from pipeline.pdf_validate import (
    MIN_PDF_BYTES,
    PDF_CORRUPT_MESSAGE,
    TAIL_SCAN_BYTES,
    validate_downloaded_pdf,
    validate_pdf_bytes,
)
from pipeline.score_pdf import score_has_archived_pdf, score_ready_for_reuse


def _valid_pdf_bytes(extra: int = 0) -> bytes:
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"xref\n0 1\n"
        b"trailer\n<< /Size 1 /Root 1 0 R >>\n"
        b"startxref\n9\n"
        b"%%EOF\n"
    )
    if len(body) + extra < MIN_PDF_BYTES:
        body += b"%" + b"x" * (MIN_PDF_BYTES - len(body) - extra)
    return body


def test_score_has_archived_pdf_requires_s3_and_size() -> None:
    assert score_has_archived_pdf(s3=True, file_size=1024) is True
    assert score_has_archived_pdf(s3=False, file_size=1024) is False
    assert score_has_archived_pdf(s3=True, file_size=0) is False
    assert score_has_archived_pdf(s3=True, file_size=None) is False


def test_score_ready_for_reuse_requires_convert_and_pages() -> None:
    from datetime import datetime

    now = datetime.utcnow()
    assert score_ready_for_reuse(convert_complete=now, num_pages=3) is True
    assert score_ready_for_reuse(convert_complete=now, num_pages=0) is False
    assert score_ready_for_reuse(convert_complete=None, num_pages=3) is False


def test_validate_pdf_bytes_accepts_structured_pdf() -> None:
    validate_pdf_bytes(_valid_pdf_bytes())


def test_validate_pdf_bytes_rejects_small_file() -> None:
    with pytest.raises(ValueError, match="too small"):
        validate_pdf_bytes(b"%PDF")


def test_validate_pdf_bytes_rejects_non_pdf() -> None:
    with pytest.raises(ValueError, match="not a PDF"):
        validate_pdf_bytes(b"<?xml version='1.0'?>" + b"x" * MIN_PDF_BYTES)


def test_validate_pdf_bytes_rejects_missing_eof() -> None:
    data = b"%PDF-1.4\n" + b"x" * MIN_PDF_BYTES
    with pytest.raises(ValueError, match=PDF_CORRUPT_MESSAGE):
        validate_pdf_bytes(data)


def test_validate_pdf_bytes_rejects_early_eof_only() -> None:
    """Linearized PDFs put %%EOF near the start; a truncated body must still fail."""
    early = (
        b"%PDF-1.6\n"
        b"startxref\n0\n"
        b"%%EOF\n"
    )
    data = early + b"x" * (TAIL_SCAN_BYTES + MIN_PDF_BYTES)
    with pytest.raises(ValueError, match=PDF_CORRUPT_MESSAGE):
        validate_pdf_bytes(data)


def test_validate_downloaded_pdf_accepts_structured_file(tmp_path: Path) -> None:
    path = tmp_path / "score.pdf"
    path.write_bytes(_valid_pdf_bytes())
    validate_downloaded_pdf(path)


def test_validate_downloaded_pdf_rejects_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "score.pdf"
    path.write_bytes(b"%PDF-1.4\n" + b"x" * MIN_PDF_BYTES)
    with pytest.raises(ValueError, match=PDF_CORRUPT_MESSAGE):
        validate_downloaded_pdf(path)

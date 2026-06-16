from pathlib import Path

import pytest

from pipeline.pdf_validate import MIN_PDF_BYTES, validate_downloaded_pdf
from pipeline.score_pdf import score_has_archived_pdf


def test_score_has_archived_pdf_requires_s3_and_size() -> None:
    assert score_has_archived_pdf(s3=True, file_size=1024) is True
    assert score_has_archived_pdf(s3=False, file_size=1024) is False
    assert score_has_archived_pdf(s3=True, file_size=0) is False
    assert score_has_archived_pdf(s3=True, file_size=None) is False


def test_validate_downloaded_pdf_accepts_real_header(tmp_path: Path) -> None:
    path = tmp_path / "score.pdf"
    path.write_bytes(b"%PDF-1.4\n" + b"x" * MIN_PDF_BYTES)
    validate_downloaded_pdf(path)


def test_validate_downloaded_pdf_rejects_small_file(tmp_path: Path) -> None:
    path = tmp_path / "score.pdf"
    path.write_bytes(b"%PDF")
    with pytest.raises(ValueError, match="too small"):
        validate_downloaded_pdf(path)


def test_validate_downloaded_pdf_rejects_non_pdf(tmp_path: Path) -> None:
    path = tmp_path / "score.pdf"
    path.write_bytes(b"<?xml version='1.0'?>" + b"x" * MIN_PDF_BYTES)
    with pytest.raises(ValueError, match="not a PDF"):
        validate_downloaded_pdf(path)

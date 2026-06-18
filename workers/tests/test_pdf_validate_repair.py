import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from pdf_validate_repair import ensure_valid_score_pdf
from pipeline.pdf_validate import PDF_CORRUPT_MESSAGE


def _valid_pdf_bytes() -> bytes:
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"xref\n0 1\n"
        b"trailer\n<< /Size 1 /Root 1 0 R >>\n"
        b"startxref\n9\n"
        b"%%EOF\n"
    )
    return body + b"x" * 1024


def test_ensure_valid_score_pdf_accepts_valid_file(tmp_path: Path) -> None:
    pdf_path = tmp_path / "score.pdf"
    workdir = tmp_path / "work"
    workdir.mkdir()
    pdf_path.write_bytes(_valid_pdf_bytes())

    ensure_valid_score_pdf(pdf_path, workdir)


def test_ensure_valid_score_pdf_normalizes_when_repair_succeeds(tmp_path: Path) -> None:
    pdf_path = tmp_path / "score.pdf"
    workdir = tmp_path / "work"
    workdir.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 1024)

    normalized = workdir / "score_normalized.pdf"
    normalized.write_bytes(_valid_pdf_bytes())

    with patch("pdf_validate_repair.validate_downloaded_pdf") as validate, patch(
        "pdf_validate_repair.normalize_pdf_for_convert"
    ) as normalize:
        validate.side_effect = [ValueError(PDF_CORRUPT_MESSAGE), None]
        ensure_valid_score_pdf(pdf_path, workdir)

    normalize.assert_called_once()


def test_ensure_valid_score_pdf_rejects_when_normalize_fails(tmp_path: Path) -> None:
    pdf_path = tmp_path / "score.pdf"
    workdir = tmp_path / "work"
    workdir.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 1024)

    with (
        patch("pdf_validate_repair.validate_downloaded_pdf", side_effect=ValueError(PDF_CORRUPT_MESSAGE)),
        patch(
            "pdf_validate_repair.normalize_pdf_for_convert",
            side_effect=subprocess.CalledProcessError(1, "gs"),
        ),
    ):
        with pytest.raises(ValueError, match=PDF_CORRUPT_MESSAGE):
            ensure_valid_score_pdf(pdf_path, workdir)

from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.pdf_validate import PDF_CORRUPT_MESSAGE
from pipeline.pdfinfo_pages import assert_pdf_has_pages


def test_assert_pdf_has_pages_accepts_positive_count(tmp_path: Path) -> None:
    path = tmp_path / "score.pdf"
    path.write_bytes(b"%PDF")

    with patch("pipeline.pdfinfo_pages.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "Pages: 12\nPage size: 612 x 792 pts\n"
        assert assert_pdf_has_pages(path) == 12


def test_assert_pdf_has_pages_rejects_zero_pages(tmp_path: Path) -> None:
    path = tmp_path / "score.pdf"
    path.write_bytes(b"%PDF")

    with patch("pipeline.pdfinfo_pages.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "Pages: 0\n"
        with pytest.raises(ValueError, match=PDF_CORRUPT_MESSAGE):
            assert_pdf_has_pages(path)


def test_assert_pdf_has_pages_rejects_pdfinfo_failure(tmp_path: Path) -> None:
    path = tmp_path / "score.pdf"
    path.write_bytes(b"%PDF")

    with patch("pipeline.pdfinfo_pages.subprocess.run") as run:
        run.return_value.returncode = 1
        run.return_value.stdout = ""
        run.return_value.stderr = "Syntax Error"
        with pytest.raises(ValueError, match=PDF_CORRUPT_MESSAGE):
            assert_pdf_has_pages(path)

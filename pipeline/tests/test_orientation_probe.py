"""Tests for fast PDF orientation probing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pipeline.orientation_probe import infer_orientation_from_page_size, infer_orientation_from_pdf


def test_infer_orientation_from_page_size_landscape() -> None:
    assert infer_orientation_from_page_size(792, 612) == "landscape"


def test_infer_orientation_from_page_size_portrait() -> None:
    assert infer_orientation_from_page_size(612, 792) == "portrait"


def test_infer_orientation_from_pdf_parses_pdfinfo(tmp_path: Path) -> None:
    pdf_path = tmp_path / "score.pdf"
    pdf_path.write_bytes(b"%PDF")

    with patch(
        "pipeline.orientation_probe.subprocess.run",
        return_value=type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "Pages: 3\nPage size: 842 x 595 pts (A4)\n",
                "stderr": "",
            },
        )(),
    ):
        assert infer_orientation_from_pdf(pdf_path) == "landscape"

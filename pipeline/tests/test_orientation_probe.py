"""Tests for fast PDF orientation probing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.pdf_rotation import pdf_effective_page_size_points, pdf_rotation_degrees
from pipeline.orientation_probe import (
    effective_page_size_pt,
    infer_orientation_from_page_size,
    infer_orientation_from_pdf,
)


def test_infer_orientation_from_page_size_landscape() -> None:
    assert infer_orientation_from_page_size(792, 612) == "landscape"


def test_infer_orientation_from_page_size_portrait() -> None:
    assert infer_orientation_from_page_size(612, 792) == "portrait"


def test_effective_page_size_swaps_on_90_and_270() -> None:
    assert effective_page_size_pt(1031, 728, 270) == (728, 1031)
    assert effective_page_size_pt(1031, 728, 90) == (728, 1031)
    assert effective_page_size_pt(1031, 728, 0) == (1031, 728)
    assert effective_page_size_pt(1031, 728, 180) == (1031, 728)


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


def test_infer_orientation_from_pdf_portrait_when_rotated_270(tmp_path: Path) -> None:
    pdf_path = tmp_path / "score.pdf"
    pdf_path.write_bytes(b"%PDF")

    with patch(
        "pipeline.orientation_probe.subprocess.run",
        return_value=type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "Pages: 5\nPage size: 1031 x 728 pts\nPage rot: 270\n",
                "stderr": "",
            },
        )(),
    ):
        assert infer_orientation_from_pdf(pdf_path) == "portrait"


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [(0, 0), (90, 90), (180, 180), (270, 270), (-90, 270)],
)
def test_pdf_rotation_degrees_reads_cardinal_metadata(
    tmp_path: Path,
    rotation: int,
    expected: int,
) -> None:
    pdf_path = tmp_path / "page.pdf"
    pdf_path.write_bytes(b"%PDF")

    with patch(
        "pipeline.pdf_rotation.subprocess.run",
        return_value=type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": f"Page size: 612 x 792 pts\nPage rot: {rotation}\n",
                "stderr": "",
            },
        )(),
    ):
        assert pdf_rotation_degrees(pdf_path) == expected


def test_pdf_rotation_degrees_ignores_noncardinal_metadata(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    pdf_path = tmp_path / "page.pdf"
    pdf_path.write_bytes(b"%PDF")

    with patch(
        "pipeline.pdf_rotation.subprocess.run",
        return_value=type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "Page size: 612 x 792 pts\nPage rot: 45\n",
                "stderr": "",
            },
        )(),
    ):
        assert pdf_rotation_degrees(pdf_path) == 0

    assert "Ignoring non-cardinal PDF /Rotate=45" in caplog.text


def test_pdf_effective_page_size_points_applies_rotation(tmp_path: Path) -> None:
    pdf_path = tmp_path / "page.pdf"
    pdf_path.write_bytes(b"%PDF")

    with patch(
        "pipeline.pdf_rotation.subprocess.run",
        return_value=type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "Page size: 612 x 792 pts\nPage rot: 90\n",
                "stderr": "",
            },
        )(),
    ):
        assert pdf_effective_page_size_points(pdf_path) == (792, 612)


def test_infer_orientation_from_pdf_accepts_negative_rotation(tmp_path: Path) -> None:
    pdf_path = tmp_path / "score.pdf"
    pdf_path.write_bytes(b"%PDF")

    with patch(
        "pipeline.orientation_probe.subprocess.run",
        return_value=type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "Page size: 1031 x 728 pts\nPage rot: -90\n",
                "stderr": "",
            },
        )(),
    ):
        assert infer_orientation_from_pdf(pdf_path) == "portrait"

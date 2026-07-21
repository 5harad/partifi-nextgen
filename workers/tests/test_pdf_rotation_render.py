"""Integration tests for rendering PDF pages with /Rotate metadata."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageOps
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

from pdf2png import par_pdf2png, pdf2png
from pipeline.page_dimensions import Orientation, get_dimensions

_PDFTK_DIRECTION = {0: "north", 90: "east", 180: "south", 270: "west"}


def _draw_page(c: canvas.Canvas, page_size: tuple[float, float], rotation: int, label: str) -> None:
    width, height = page_size
    c.setPageSize(page_size)
    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(-rotation)
    c.translate(-width / 2, -height / 2)
    c.setFont("Helvetica-Bold", 48)
    c.drawString(72, height - 110, label)
    c.restoreState()
    c.showPage()


def _make_viewer_upright_pdf(
    path: Path,
    pages: list[tuple[tuple[float, float], int, str]],
) -> None:
    physical = path.with_name(f"{path.stem}-physical.pdf")
    c = canvas.Canvas(str(physical), pagesize=pages[0][0])
    for page_size, rotation, label in pages:
        _draw_page(c, page_size, rotation, label)
    c.save()

    directions = [f"{index}{_PDFTK_DIRECTION[rotation]}" for index, (_, rotation, _) in enumerate(pages, 1)]
    subprocess.check_call(["pdftk", str(physical), "cat", *directions, "output", str(path)])


def _render_viewer_reference(pdf_path: Path, output: Path, orientation: Orientation) -> None:
    native = output.with_suffix(".native.png")
    subprocess.check_call(
        [
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=pnggray",
            "-dDOINTERPOLATE",
            "-dUseCropBox",
            "-r300",
            f"-sOutputFile={native}",
            str(pdf_path),
        ]
    )
    with Image.open(native) as source:
        size = get_dimensions(orientation).highres_size
        expected = ImageOps.contain(source, size, Image.LANCZOS)
        canvas = Image.new(source.mode, size, 255)
        canvas.paste(expected, ((size[0] - expected.width) // 2, (size[1] - expected.height) // 2))
        canvas.save(output)


def _make_output_dirs(path: Path) -> None:
    for kind in ("highres", "lowres", "thumbs"):
        (path / kind).mkdir(parents=True)


@pytest.mark.parametrize(
    ("rotation", "orientation"),
    [(0, "portrait"), (90, "landscape"), (180, "portrait"), (270, "landscape")],
)
def test_pdf2png_matches_pdf_viewer_orientation(
    tmp_path: Path,
    rotation: int,
    orientation: Orientation,
) -> None:
    if not shutil.which("pdftk"):
        pytest.skip("pdftk is required for PDF rotation integration tests")

    pdf_path = tmp_path / f"rotation-{rotation}.pdf"
    _make_viewer_upright_pdf(pdf_path, [(letter, rotation, f"rotation {rotation}")])

    output = tmp_path / "output"
    _make_output_dirs(output)
    pdf2png(str(pdf_path), str(output), None, 1, orientation=orientation)

    expected = tmp_path / "expected.png"
    _render_viewer_reference(pdf_path, expected, orientation)
    actual = output / "highres" / f"rotation-{rotation}.png"
    with Image.open(actual) as actual_im, Image.open(expected) as expected_im:
        assert ImageChops.difference(actual_im, expected_im).getbbox() is None


def test_pdf2png_renders_mixed_metadata_rotations_upright(tmp_path: Path) -> None:
    if not shutil.which("pdftk"):
        pytest.skip("pdftk is required for PDF rotation integration tests")

    pdf_path = tmp_path / "mixed.pdf"
    _make_viewer_upright_pdf(
        pdf_path,
        [
            (letter, 0, "portrait"),
            (landscape(letter), 90, "rotated"),
            (letter, 180, "inverted"),
        ],
    )

    output = tmp_path / "output"
    _make_output_dirs(output)
    par_pdf2png(str(pdf_path), str(output), None, orientation="portrait")

    burst_dir = tmp_path / "burst"
    burst_dir.mkdir()
    subprocess.check_call(["pdftk", str(pdf_path), "burst", "output", str(burst_dir / "page-%d.pdf")])
    for page in range(1, 4):
        expected = tmp_path / f"expected-{page}.png"
        _render_viewer_reference(burst_dir / f"page-{page}.pdf", expected, "portrait")
        actual = output / "highres" / f"page-{page}.png"
        with Image.open(actual) as actual_im, Image.open(expected) as expected_im:
            assert ImageChops.difference(actual_im, expected_im).getbbox() is None

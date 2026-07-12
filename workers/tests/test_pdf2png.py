"""Tests for orientation-aware PDF to PNG conversion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pdf2png import _detect_orientation_from_burst, pdf2png


def test_pdf2png_uses_landscape_canvas_sizes(tmp_path: Path) -> None:
    outdir = tmp_path / "pages"
    for sub in ("highres", "lowres", "thumbs"):
        (outdir / sub).mkdir(parents=True)

    page_pdf = tmp_path / "page-1.pdf"
    page_pdf.write_bytes(b"%PDF-1.4")

    highres_png = outdir / "highres" / "page-1.png"
    highres_png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x0c\xe4\x00\x00\t\xf6\x08\x00\x00\x00\x00\x00\x00"
    )

    with (
        patch("pdf2png.run_subprocess_with_repair") as run_gs,
        patch("pdf2png.Image.open") as image_open,
    ):
        image_open.return_value.resize.side_effect = lambda size, _resample: MagicMock(size=size)
        pdf2png(str(page_pdf), str(outdir), None, 1, orientation="landscape")

    gs_cmd = run_gs.call_args.args[0]
    assert "-g3300x2550" in gs_cmd
    resize_sizes = [call.args[0] for call in image_open.return_value.resize.call_args_list]
    assert (776, 600) in resize_sizes
    assert (129, 100) in resize_sizes


def test_pdf2png_defaults_to_portrait_canvas_sizes(tmp_path: Path) -> None:
    outdir = tmp_path / "pages"
    for sub in ("highres", "lowres", "thumbs"):
        (outdir / sub).mkdir(parents=True)

    page_pdf = tmp_path / "page-1.pdf"
    page_pdf.write_bytes(b"%PDF-1.4")

    highres_png = outdir / "highres" / "page-1.png"
    highres_png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\t\xf6\x00\x00\x0c\xe4\x08\x00\x00\x00\x00\x00\x00"
    )

    with (
        patch("pdf2png.run_subprocess_with_repair") as run_gs,
        patch("pdf2png.Image.open") as image_open,
    ):
        image_open.return_value.resize.side_effect = lambda size, _resample: MagicMock(size=size)
        pdf2png(str(page_pdf), str(outdir), None, 1)

    gs_cmd = run_gs.call_args.args[0]
    assert "-g2550x3300" in gs_cmd
    resize_sizes = [call.args[0] for call in image_open.return_value.resize.call_args_list]
    assert (600, 776) in resize_sizes
    assert (100, 129) in resize_sizes


def test_detect_orientation_from_burst_uses_page_one(tmp_path: Path) -> None:
    burst_dir = tmp_path / "burst"
    burst_dir.mkdir()
    (burst_dir / "page-2.pdf").write_bytes(b"%PDF")
    page_one = burst_dir / "page-1.pdf"
    page_one.write_bytes(b"%PDF")

    native_im = MagicMock()
    with (
        patch("pdf2png.render_page_native_lowres", return_value=native_im) as render,
        patch(
            "pdf2png.detect_orientation_from_images",
            return_value=MagicMock(orientation="landscape"),
        ),
    ):
        orientation = _detect_orientation_from_burst(str(burst_dir))

    assert orientation == "landscape"
    render.assert_called_once_with(page_one, burst_dir / "orient-detect")

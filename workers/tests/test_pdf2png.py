"""Tests for orientation-aware PDF to PNG conversion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from pdf2png import _detect_orientation_from_burst, _fit_image_to_canvas, par_pdf2png, pdf2png


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
        patch("pdf2png._fit_image_to_canvas") as fit,
        patch("pdf2png.pdf_effective_page_size_points", return_value=(792, 612)),
    ):
        rendered = MagicMock()
        fit.return_value = rendered
        pdf2png(str(page_pdf), str(outdir), None, 1, orientation="landscape")

    gs_cmd = run_gs.call_args.args[0]
    assert "-r300" in gs_cmd
    fit.assert_called_once_with(image_open.return_value.__enter__.return_value, (3300, 2550))
    resize_sizes = [call.args[0] for call in rendered.resize.call_args_list]
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
        patch("pdf2png._fit_image_to_canvas") as fit,
        patch("pdf2png.pdf_effective_page_size_points", return_value=(612, 792)),
    ):
        rendered = MagicMock()
        fit.return_value = rendered
        pdf2png(str(page_pdf), str(outdir), None, 1)

    gs_cmd = run_gs.call_args.args[0]
    assert "-r300" in gs_cmd
    fit.assert_called_once_with(image_open.return_value.__enter__.return_value, (2550, 3300))
    resize_sizes = [call.args[0] for call in rendered.resize.call_args_list]
    assert (600, 776) in resize_sizes
    assert (100, 129) in resize_sizes


def test_pdf2png_caps_native_render_resolution_for_large_pages(tmp_path: Path) -> None:
    outdir = tmp_path / "pages"
    for sub in ("highres", "lowres", "thumbs"):
        (outdir / sub).mkdir(parents=True)
    page_pdf = tmp_path / "page-1.pdf"
    page_pdf.write_bytes(b"%PDF-1.4")

    with (
        patch("pdf2png.run_subprocess_with_repair") as run_gs,
        patch("pdf2png.Image.open") as image_open,
        patch("pdf2png._fit_image_to_canvas", return_value=MagicMock()),
        patch("pdf2png.pdf_effective_page_size_points", return_value=(1728, 2592)),
    ):
        pdf2png(str(page_pdf), str(outdir), None, 1)

    assert "-r91" in run_gs.call_args.args[0]


def test_fit_image_to_canvas_preserves_a4_aspect_ratio() -> None:
    source = Image.new("L", (595, 842), 255)
    source.putpixel((0, 0), 0)
    fitted = _fit_image_to_canvas(source, (2550, 3300))

    assert fitted.size == (2550, 3300)
    assert fitted.getpixel((109, 0)) == 0
    assert fitted.getpixel((0, 0)) == 255


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


def test_par_pdf2png_processes_each_burst_page(tmp_path: Path) -> None:
    input_pdf = tmp_path / "score.pdf"
    input_pdf.write_bytes(b"%PDF")
    outdir = tmp_path / "pages"

    def burst(_pdf: str, tempdir: str) -> None:
        Path(tempdir, "page-1.pdf").write_bytes(b"%PDF")
        Path(tempdir, "page-2.pdf").write_bytes(b"%PDF")

    with (
        patch("pdf2png.burst_score_pages", side_effect=burst),
        patch("pdf2png.map_in_parallel") as render,
    ):
        par_pdf2png(str(input_pdf), str(outdir), None, orientation="portrait")

    assert len(render.call_args.args[1]) == 2

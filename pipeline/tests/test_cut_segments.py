"""Tests for segment cut height helpers."""

from pathlib import Path

import pytest
from PIL import Image

from pipeline.cut_segments import (
    cut_segments_on_image,
    read_segment_png_heights,
    scaled_preview_segment_heights,
    segment_cut_height_px,
    segment_heights_for_rows,
)
from pipeline.cutpaste import page_chunks
from pipeline.page_dimensions import prct2pixel


def test_segment_cut_height_matches_crop(tmp_path: Path) -> None:
    page = tmp_path / "page.png"
    Image.new("L", (2550, 3300), 255).save(page)
    out = tmp_path / "seg.png"
    cut_segments_on_image(page, 0.0, [(0.0, 10.0, 100.0, 20.0, out)])
    with Image.open(out) as seg:
        assert seg.size[1] == segment_cut_height_px(10.0, 20.0, "portrait")


def test_segment_cut_height_matches_prct2pixel_within_one_pixel() -> None:
    pct = 10.15
    float_h = prct2pixel(pct, "height", "portrait")
    cut_h = segment_cut_height_px(10.0, 10.0 + pct, "portrait")
    assert abs(cut_h - float_h) <= 1.0


def test_segment_cut_height_uses_actual_page_height(tmp_path: Path) -> None:
    page = tmp_path / "page.png"
    Image.new("L", (2550, 3299), 255).save(page)
    out = tmp_path / "seg.png"
    top, bottom = 10.0, 20.15
    cut_segments_on_image(page, 0.0, [(0.0, top, 100.0, bottom, out)])
    with Image.open(out) as seg:
        png_h = seg.size[1]
    nominal = segment_cut_height_px(top, bottom, "portrait")
    actual = segment_cut_height_px(top, bottom, "portrait", page_height_px=3299)
    assert png_h == actual
    assert actual != nominal


def test_segment_heights_for_rows_matches_png_cuts(tmp_path: Path) -> None:
    page = tmp_path / "page.png"
    Image.new("L", (2550, 3300), 255).save(page)
    rows = []
    for i in range(4):
        top = 5.0 + i * 4.7
        bottom = top + 4.5
        out = tmp_path / f"s{i}.png"
        cut_segments_on_image(page, 0.0, [(0.0, top, 100.0, bottom, out)])
        rows.append({"page": 1, "top": top, "bottom": bottom})

    png_heights = read_segment_png_heights(tmp_path, 4)
    formula_heights = segment_heights_for_rows(rows, "portrait", {1: 3300})
    assert formula_heights == png_heights


def test_page_chunks_with_measured_png_heights(tmp_path: Path) -> None:
    page = tmp_path / "page.png"
    Image.new("L", (2550, 3300), 255).save(page)
    for i in range(3):
        top = 10.0 + i * 10.15
        bottom = top + 10.15
        cut_segments_on_image(page, 0.0, [(0.0, top, 100.0, bottom, tmp_path / f"s{i}.png")])

    png_heights = read_segment_png_heights(tmp_path, 3)
    assert all(h == segment_cut_height_px(10.0 + i * 10.15, 10.0 + (i + 1) * 10.15, "portrait")
               for i, h in enumerate(png_heights))
    chunks = page_chunks([0, 1, 2], png_heights, 30, orientation="portrait")
    assert chunks


def test_scaled_preview_segment_heights_matches_highres_cut(tmp_path: Path) -> None:
    lowres_page = tmp_path / "lowres.png"
    highres_page = tmp_path / "highres.png"
    Image.new("L", (600, 776), 255).save(lowres_page)
    Image.new("L", (2550, 3300), 255).save(highres_page)

    top, bottom = 10.0, 20.0
    preview_dir = tmp_path / "preview"
    highres_dir = tmp_path / "highres"
    preview_dir.mkdir()
    highres_dir.mkdir()
    cut_segments_on_image(lowres_page, 5.0, [(0.0, top, 100.0, bottom, preview_dir / "s0.png")])
    cut_segments_on_image(highres_page, 5.0, [(0.0, top, 100.0, bottom, highres_dir / "s0.png")])

    rows = [{"page": 1, "top": top, "bottom": bottom}]
    scaled = scaled_preview_segment_heights(
        preview_dir,
        rows,
        highres_page_heights={1: 3300},
        lowres_page_heights={1: 776},
    )
    assert scaled[0] == pytest.approx(read_segment_png_heights(highres_dir, 1)[0], abs=2.0)

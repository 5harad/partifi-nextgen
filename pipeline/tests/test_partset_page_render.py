"""Tests for oriented partset page rendering."""

from __future__ import annotations

from PIL import Image

from pipeline.page_dimensions import LANDSCAPE, PORTRAIT
from pipeline.partset_page_render import render_oriented_page, rotate_page_image


def test_render_oriented_page_keeps_landscape_at_zero_degrees() -> None:
    source = Image.new("L", LANDSCAPE.highres_size, 255)
    out = render_oriented_page(
        source,
        score_orientation="landscape",
        rotation_degrees=0,
        kind="lowres",
    )
    assert out.size == LANDSCAPE.lowres_size


def test_render_oriented_page_rotates_landscape_score_to_portrait_layout() -> None:
    source = Image.new("L", LANDSCAPE.highres_size, 255)
    out = render_oriented_page(
        source,
        score_orientation="landscape",
        rotation_degrees=90,
        kind="lowres",
    )
    assert out.size == PORTRAIT.lowres_size


def test_render_oriented_page_matches_preview_and_segment_pipeline() -> None:
    source = Image.new("L", LANDSCAPE.lowres_size, 0)
    source.putpixel((LANDSCAPE.lowres_width - 1, 0), 255)
    segment = render_oriented_page(
        source.copy(),
        score_orientation="landscape",
        rotation_degrees=270,
        kind="lowres",
    )
    assert segment.size == PORTRAIT.lowres_size


def test_rotate_page_image_swaps_dimensions_at_90_degrees() -> None:
    source = Image.new("L", LANDSCAPE.lowres_size, 255)
    out = rotate_page_image(source, 90)
    assert out.size == (LANDSCAPE.lowres_height, LANDSCAPE.lowres_width)


def test_rotate_page_image_leaves_zero_degrees_unchanged() -> None:
    source = Image.new("L", LANDSCAPE.lowres_size, 255)
    out = rotate_page_image(source, 0)
    assert out.size == LANDSCAPE.lowres_size

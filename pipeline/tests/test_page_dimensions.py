"""Tests for page dimension helpers."""

from pipeline.cutpaste import preview_left_margin
from pipeline.page_dimensions import LANDSCAPE, PORTRAIT, get_dimensions, prct2pixel


def test_portrait_dimensions_match_legacy_constants() -> None:
    assert PORTRAIT.highres_width == 2550
    assert PORTRAIT.highres_height == 3300
    assert PORTRAIT.lowres_width == 600
    assert PORTRAIT.lowres_height == 776


def test_landscape_dimensions_swap_aspect() -> None:
    assert LANDSCAPE.highres_width == 3300
    assert LANDSCAPE.highres_height == 2550
    assert LANDSCAPE.lowres_width == 776
    assert LANDSCAPE.lowres_height == 600


def test_prct2pixel_portrait_height() -> None:
    assert prct2pixel(50, "height", "portrait") == 1650.0


def test_prct2pixel_landscape_width() -> None:
    assert prct2pixel(50, "width", "landscape") == 1650.0


def test_get_dimensions() -> None:
    assert get_dimensions("portrait").orientation == "portrait"
    assert get_dimensions("landscape").orientation == "landscape"


def test_page_chunk_max_and_preview_pane() -> None:
    assert PORTRAIT.page_chunk_max == 2900
    assert LANDSCAPE.page_chunk_max == 2150
    assert PORTRAIT.preview_pane_width == 367
    assert LANDSCAPE.preview_pane_width == 475


def test_preview_left_margin_scales_with_orientation() -> None:
    assert preview_left_margin([80.0], orientation="portrait") == 37
    assert preview_left_margin([80.0], orientation="landscape") == 47

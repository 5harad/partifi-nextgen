"""Tests for part PDF layout helpers."""

import pytest

from pipeline.paste_layout import (
    CONTENT_START_OFFSET,
    page_dims_inches,
    paste_content_bottom_in,
    paste_content_height_in,
    paste_packing_bottom_in,
    paste_packing_top_in,
    paste_page_chunk_max_px,
    vertical_layout,
)


def test_paste_page_chunk_max_portrait_fits_letter_and_a4() -> None:
    assert paste_page_chunk_max_px("portrait") == 2865
    letter_in = paste_content_height_in("letter", "portrait")
    a4_in = paste_content_height_in("a4", "portrait")
    assert letter_in == pytest.approx(9.55)
    assert a4_in == pytest.approx(9.55)


def test_paste_page_chunk_max_landscape_fits_letter_and_a4() -> None:
    assert paste_page_chunk_max_px("landscape") == 1925
    letter_in = paste_content_height_in("letter", "landscape")
    a4_in = paste_content_height_in("a4", "landscape")
    assert a4_in < letter_in


def test_vertical_layout_landscape() -> None:
    bottom, top = vertical_layout(8.5, "landscape")
    assert bottom == 0.4
    assert top == 8.0


def test_paste_content_bottom_reserves_footer_band() -> None:
    bottom_margin, _ = vertical_layout(11, "portrait")
    assert paste_content_bottom_in("letter", "portrait") == bottom_margin + 0.25


def test_landscape_letter_packing_zone_matches_a4_height() -> None:
    letter_top = paste_packing_top_in("letter", "landscape")
    letter_bottom = paste_packing_bottom_in("letter", "landscape")
    assert letter_top - letter_bottom == pytest.approx(paste_content_height_in("a4", "landscape"))


def test_landscape_letter_packing_is_centered() -> None:
    pad = (
        paste_content_height_in("letter", "landscape")
        - paste_content_height_in("a4", "landscape")
    ) / 2
    _, letter_h = page_dims_inches("letter", "landscape")
    _, top_margin = vertical_layout(letter_h, "landscape")
    raw_top = top_margin - CONTENT_START_OFFSET
    assert paste_packing_top_in("letter", "landscape") == pytest.approx(raw_top - pad)
    assert paste_packing_bottom_in("letter", "landscape") == pytest.approx(
        paste_content_bottom_in("letter", "landscape") + pad
    )


def test_a4_landscape_packing_matches_content_band() -> None:
    _, page_h = page_dims_inches("a4", "landscape")
    _, top_margin = vertical_layout(page_h, "landscape")
    assert paste_packing_top_in("a4", "landscape") == pytest.approx(
        top_margin - CONTENT_START_OFFSET
    )
    assert paste_packing_bottom_in("a4", "landscape") == paste_content_bottom_in(
        "a4", "landscape"
    )

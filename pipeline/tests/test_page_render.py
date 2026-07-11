"""Tests for native page render DPI selection."""

from pipeline.page_render import NATIVE_LOWRES_MAX_SIDE, NATIVE_RENDER_DPI, _dpi_for_max_side


def test_dpi_for_letter_page_caps_at_lowres_target() -> None:
    # US Letter in points
    dpi = _dpi_for_max_side(612, 792)
    assert dpi < NATIVE_RENDER_DPI
    assert round(792 * dpi / 72) <= NATIVE_LOWRES_MAX_SIDE


def test_dpi_for_small_page_stays_within_max_side() -> None:
    dpi = _dpi_for_max_side(200, 300)
    assert round(300 * dpi / 72) <= NATIVE_LOWRES_MAX_SIDE


def test_dpi_for_oversized_page_avoids_huge_raster() -> None:
    # Very large format score page (~40" tall)
    dpi = _dpi_for_max_side(2000, 2880)
    assert dpi < 50
    assert round(2880 * dpi / 72) <= NATIVE_LOWRES_MAX_SIDE

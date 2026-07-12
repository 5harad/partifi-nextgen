"""Part PDF page layout — content band, footer, and chunk height limits."""

from __future__ import annotations

from pipeline.page_dimensions import Orientation

RESOLUTION = 300.0
FOOTER_BAND_IN = 0.25
CONTENT_START_OFFSET = 0.7
PAGE_SIZES_IN = {"letter": (8.5, 11), "a4": (8.27, 11.69)}


def page_dims_inches(pagesize: str, orientation: Orientation) -> tuple[float, float]:
    width, height = PAGE_SIZES_IN[pagesize]
    if orientation == "landscape":
        return height, width
    return width, height


def vertical_layout(page_h: float, orientation: Orientation) -> tuple[float, float]:
    """Return (bottom_margin, top_margin) in inches from the page bottom."""
    if orientation == "landscape":
        return 0.4, page_h - 0.5
    bottom_margin = (page_h - 10.5) / 2
    return bottom_margin, bottom_margin + 10.5


def paste_content_height_in(pagesize: str, orientation: Orientation) -> float:
    """Vertical space (inches) available for segment images on one PDF page."""
    _, page_h = page_dims_inches(pagesize, orientation)
    bottom_margin, top_margin = vertical_layout(page_h, orientation)
    content_top = top_margin - CONTENT_START_OFFSET
    content_bottom = bottom_margin + FOOTER_BAND_IN
    return content_top - content_bottom


def paste_content_bottom_in(pagesize: str, orientation: Orientation) -> float:
    """Minimum Y (inches from page bottom) for the bottom edge of segment images."""
    _, page_h = page_dims_inches(pagesize, orientation)
    bottom_margin, _ = vertical_layout(page_h, orientation)
    return bottom_margin + FOOTER_BAND_IN


def _landscape_letter_packing_pad_in() -> float:
    """Pad above/below the A4 packing zone when centering on letter landscape."""
    return (
        paste_content_height_in("letter", "landscape")
        - paste_content_height_in("a4", "landscape")
    ) / 2


def paste_packing_top_in(pagesize: str, orientation: Orientation) -> float:
    """Y from page bottom where segment stacking begins."""
    _, page_h = page_dims_inches(pagesize, orientation)
    _, top_margin = vertical_layout(page_h, orientation)
    top = top_margin - CONTENT_START_OFFSET
    if orientation == "landscape" and pagesize == "letter":
        top -= _landscape_letter_packing_pad_in()
    return top


def paste_packing_bottom_in(pagesize: str, orientation: Orientation) -> float:
    """Minimum Y from page bottom for the bottom edge of stacked segment images."""
    floor_in = paste_content_bottom_in(pagesize, orientation)
    if orientation == "landscape" and pagesize == "letter":
        floor_in += _landscape_letter_packing_pad_in()
    return floor_in


def paste_page_chunk_max_px(orientation: Orientation) -> int:
    """Max stacked segment height (px at 300 dpi) for letter and A4 content bands."""
    height_in = min(
        paste_content_height_in("letter", orientation),
        paste_content_height_in("a4", orientation),
    )
    return int(height_in * RESOLUTION)

"""Create a viewer-oriented, vector-preserving two-up PDF in worker scratch space."""

from __future__ import annotations

from pathlib import Path

import fitz

from pipeline.partset_orientation import normalize_rotation_degrees


def split_two_up_pdf(
    source_pdf: Path,
    output_pdf: Path,
    *,
    rotation_degrees: int,
) -> int:
    """Apply the user rotation, then emit the left and right halves of each page.

    ``show_pdf_page`` copies PDF objects rather than rasterizing them.  The intermediate
    document has the same viewer orientation as the orientation-page preview; clipping it
    there makes the split independent of the source PDF's `/Rotate` metadata.
    """
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    source = fitz.open(source_pdf)
    oriented = fitz.open()
    result = fitz.open()
    try:
        # Flatten each source `/Rotate` into its page contents first.  PyMuPDF's
        # `show_pdf_page` otherwise composes that metadata differently from the
        # Ghostscript viewer rendering used elsewhere in the application.
        for source_page in source:
            source_page.remove_rotation()

        for page_number, source_page in enumerate(source):
            source_rect = source_page.rect
            width, height = source_rect.width, source_rect.height
            if rotation_degrees % 180 == 90:
                width, height = height, width
            oriented_page = oriented.new_page(width=width, height=height)
            oriented_page.show_pdf_page(
                oriented_page.rect,
                source,
                page_number,
                # PyMuPDF uses clockwise rotation while the orientation preview
                # (Pillow) uses counter-clockwise positive degrees.
                rotate=(-rotation_degrees) % 360,
            )

        for page_number, page in enumerate(oriented):
            rect = page.rect
            if rect.width <= rect.height:
                raise ValueError("Two-column splitting requires landscape pages after rotation")
            midpoint = rect.width / 2
            for clip in (
                fitz.Rect(rect.x0, rect.y0, midpoint, rect.y1),
                fitz.Rect(midpoint, rect.y0, rect.x1, rect.y1),
            ):
                split_page = result.new_page(width=clip.width, height=clip.height)
                split_page.show_pdf_page(split_page.rect, oriented, page_number, clip=clip)
        result.save(output_pdf, garbage=4, deflate=True)
        return len(result)
    finally:
        result.close()
        oriented.close()
        source.close()
